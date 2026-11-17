import json
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import ProductVariant
from cart.models import StockReservation
from orders.models import Order
from .models import PaymentTransaction, RefundRecord
from .razorpay_client import (
    dispatch_razorpay_refund,
    verify_payment_signature,
    verify_webhook_signature,
)
from .serializers import (
    PaymentTransactionSerializer,
    RazorpayVerifySerializer,
    RefundRecordSerializer,
)

logger = logging.getLogger(__name__)


def process_payment_capture(
    order: Order,
    payment_id: str,
    signature: str = None,
    raw_payload: dict = None,
) -> dict:
    """
    Atomic, idempotent processor for online payment captures.
    Coordinates between synchronous verification and asynchronous webhooks.
    Handles standard conversions and complex late-payment oversell edge cases.
    """
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(id=order.id)

        # 1. Strict Idempotency Guard
        if locked_order.payment_status == 'Paid':
            return {
                'status': 'already_processed',
                'message': 'Payment already processed and verified.',
                'order': locked_order,
            }

        # 2. Check active stock reservations
        reservations = StockReservation.objects.filter(
            order_number=locked_order.order_number,
            status=StockReservation.STATUS_ACTIVE,
        )

        if reservations.exists():
            # Scenario A: Payment captured while reservation is ACTIVE within 15-min TTL
            for res in reservations:
                res.convert_to_sale()

            locked_order.payment_status = 'Paid'
            locked_order.order_status = 'Ordered'
            locked_order.razorpay_payment_id = payment_id
            locked_order.save(update_fields=['payment_status', 'order_status', 'razorpay_payment_id', 'updated_at'])

            PaymentTransaction.objects.update_or_create(
                order=locked_order,
                gateway_order_id=locked_order.razorpay_order_id or '',
                defaults={
                    'gateway': 'razorpay',
                    'gateway_payment_id': payment_id,
                    'gateway_signature': signature or '',
                    'amount': locked_order.total_amount,
                    'status': PaymentTransaction.STATUS_CAPTURED,
                    'raw_response': raw_payload or {},
                },
            )

            return {
                'status': 'success',
                'message': 'Payment verified successfully.',
                'order': locked_order,
            }

        # Scenario B: Late Payment — Reservation has EXPIRED or was released
        # Inspect available unreserved stock across all line items
        has_insufficient_stock = False
        items_variants = []

        for item in locked_order.items.select_related('variant'):
            if not item.variant:
                has_insufficient_stock = True
                break

            locked_v = ProductVariant.objects.select_for_update().get(id=item.variant.id)
            unreserved_stock = max(0, locked_v.stock - locked_v.reserved_stock)
            if unreserved_stock < item.quantity:
                has_insufficient_stock = True
                break
            items_variants.append((locked_v, item.quantity))

        if not has_insufficient_stock:
            # Sub-scenario B1: Unreserved stock is still available; allocate without touching others' holds
            for locked_v, qty in items_variants:
                ProductVariant.objects.filter(id=locked_v.id).update(stock=F('stock') - qty)

            locked_order.payment_status = 'Paid'
            locked_order.order_status = 'Ordered'
            locked_order.razorpay_payment_id = payment_id
            locked_order.save(update_fields=['payment_status', 'order_status', 'razorpay_payment_id', 'updated_at'])

            PaymentTransaction.objects.update_or_create(
                order=locked_order,
                gateway_order_id=locked_order.razorpay_order_id or '',
                defaults={
                    'gateway': 'razorpay',
                    'gateway_payment_id': payment_id,
                    'gateway_signature': signature or '',
                    'amount': locked_order.total_amount,
                    'status': PaymentTransaction.STATUS_CAPTURED,
                    'raw_response': {'note': 'Late payment captured - Unreserved stock allocated: Converted to Sale'},
                },
            )

            return {
                'status': 'late_payment_allocated',
                'message': 'Late payment verified and unreserved stock allocated.',
                'order': locked_order,
            }

        # Sub-scenario B2: Oversold / Depleted Inventory
        # DO NOT decrement stock below zero! DO NOT consume other customers' reservations!
        locked_order.payment_status = 'Paid'
        locked_order.order_status = 'Requires_Attention'
        locked_order.razorpay_payment_id = payment_id
        locked_order.save(update_fields=['payment_status', 'order_status', 'razorpay_payment_id', 'updated_at'])

        txn, _ = PaymentTransaction.objects.update_or_create(
            order=locked_order,
            gateway_order_id=locked_order.razorpay_order_id or '',
            defaults={
                'gateway': 'razorpay',
                'gateway_payment_id': payment_id,
                'gateway_signature': signature or '',
                'amount': locked_order.total_amount,
                'status': PaymentTransaction.STATUS_CAPTURED,
                'raw_response': {'error': 'Late payment on depleted inventory. Requires manual attention or automated refund.'},
            },
        )

        idempotency_key = f"refund-late-{locked_order.order_number}"
        refund_record, created = RefundRecord.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                'order': locked_order,
                'payment': txn,
                'amount': locked_order.total_amount,
                'reason': 'Late payment on depleted inventory',
                'status': RefundRecord.STATUS_PENDING,
            },
        )

        # Attempt immediate dispatch if possible
        try:
            res = dispatch_razorpay_refund(
                payment_id=payment_id,
                amount_paise=int(locked_order.total_amount * 100),
                idempotency_key=idempotency_key,
                reason='Late payment on depleted inventory',
            )
            refund_record.razorpay_refund_id = res.get('id')
            refund_record.status = RefundRecord.STATUS_PROCESSED
            refund_record.save(update_fields=['razorpay_refund_id', 'status', 'updated_at'])
        except Exception as e:
            logger.warning(f"Immediate refund dispatch failed, queued for background retry: {e}")

        return {
            'status': 'requires_attention',
            'message': 'Late payment captured but stock was depleted; order transitioned to Requires_Attention and refund queued.',
            'order': locked_order,
        }


class RazorpayVerifyView(APIView):
    """
    Primary synchronous endpoint verifying customer payment signature.
    POST /api/payments/razorpay/verify/
    Aligns with Section 3.3 of docs/backend/05_API_CONTRACT.md.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RazorpayVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_id = serializer.validated_data['razorpay_order_id']
        payment_id = serializer.validated_data['razorpay_payment_id']
        signature = serializer.validated_data['razorpay_signature']

        # 1. Verify cryptographic HMAC signature
        is_valid = verify_payment_signature(order_id, payment_id, signature)
        if not is_valid:
            return Response(
                {'error': "Invalid payment signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Match order by razorpay_order_id
        order = get_object_or_404(Order, razorpay_order_id=order_id, user=request.user)

        # 3. Process capture
        result = process_payment_capture(order, payment_id, signature, raw_payload=request.data)

        return Response(
            {
                'message': result['message'],
                'order_id': order.id,
                'order_number': order.order_number,
                'order_status': result['order'].order_status,
                'payment_status': result['order'].payment_status,
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(APIView):
    """
    Asynchronous fallback capturing payment capture and failure notifications.
    POST /api/payments/razorpay/webhook/
    Aligns with Section 3.4 of docs/backend/05_API_CONTRACT.md.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        signature_header = request.headers.get('X-Razorpay-Signature', '')
        raw_body = request.body

        if not verify_webhook_signature(raw_body, signature_header):
            return Response(
                {'error': "Invalid webhook signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except Exception:
            return Response({'error': "Invalid JSON payload."}, status=status.HTTP_400_BAD_REQUEST)

        event = payload.get('event')
        if event in ('payment.captured', 'order.paid'):
            entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
            rzp_order_id = entity.get('order_id')
            payment_id = entity.get('id')

            if rzp_order_id and payment_id:
                order = Order.objects.filter(razorpay_order_id=rzp_order_id).first()
                if order:
                    process_payment_capture(order, payment_id, raw_payload=payload)

        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


class PaymentTransactionListView(generics.ListAPIView):
    """
    List transactions associated with the customer's orders.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = PaymentTransactionSerializer

    def get_queryset(self):
        return PaymentTransaction.objects.filter(order__user=self.request.user).order_by('-created_at')


class RefundRecordListView(generics.ListAPIView):
    """
    List refund records associated with the customer's orders.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RefundRecordSerializer

    def get_queryset(self):
        return RefundRecord.objects.filter(order__user=self.request.user).order_by('-created_at')

