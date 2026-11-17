import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import SavedAddress
from catalog.models import Category, Color, Product, ProductVariant, Size
from cart.models import Cart, CartItem, StockReservation
from orders.models import Order, OrderItem
from payments.models import PaymentTransaction, RefundRecord
from payments.razorpay_client import (
    compute_payment_signature,
    verify_payment_signature,
    verify_webhook_signature,
)
from payments.tasks import process_pending_refund_records

User = get_user_model()


class PaymentsBaseTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='kavya.nair@example.com',
            first_name='Kavya',
            last_name='Nair',
            password='TestPassword123!',
        )

        self.category, _ = Category.objects.get_or_create(
            slug='co-ord-sets',
            defaults={'name': 'Co-ord Sets', 'display_order': 2},
        )
        self.color, _ = Color.objects.get_or_create(
            name='Emerald Green',
            defaults={'hex_code': '#059669'},
        )
        self.size_m, _ = Size.objects.get_or_create(
            name='M',
            defaults={'order': 2},
        )

        self.product = Product.objects.create(
            title='Emerald Festive Kurti Set',
            slug='emerald-festive-kurti-set',
            sku_prefix='SFK-EMR',
            category=self.category,
            feeding_config='both',
            price=Decimal('1599.00'),
            mrp=Decimal('2299.00'),
            is_active=True,
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            clothing_type='Feeding',
            color=self.color,
            size=self.size_m,
            sku='SFK-EMR-FD-GR-M',
            stock=10,
            reserved_stock=0,
        )

        self.saved_address = SavedAddress.objects.create(
            user=self.user,
            recipient_name='Kavya Nair',
            phone='9876500000',
            address_line1='Flat 101, Green Heights',
            address_line2='Gachibowli',
            landmark='Near Stadium',
            city='Hyderabad',
            state='Telangana',
            pincode='500032',
            is_default=True,
        )


class CryptographicSignatureTests(PaymentsBaseTestCase):
    def test_hmac_sha256_payment_signature_verification(self):
        order_id = "order_Ox84J2kd9A"
        payment_id = "pay_Ox86La921B"
        valid_sig = compute_payment_signature(order_id, payment_id)

        # Valid signature must verify True
        self.assertTrue(verify_payment_signature(order_id, payment_id, valid_sig))

        # Tampered signature must be rejected
        self.assertFalse(verify_payment_signature(order_id, payment_id, "tampered_signature_123456"))

        # Altered payment_id must be rejected
        self.assertFalse(verify_payment_signature(order_id, "pay_Different999", valid_sig))

    def test_webhook_signature_verification(self):
        secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', 'placeholder_webhook_secret')
        body = b'{"event": "payment.captured", "payload": {}}'
        valid_sig = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()

        self.assertTrue(verify_webhook_signature(body, valid_sig))
        self.assertFalse(verify_webhook_signature(body, "invalid_sig_abc"))


class OrderCheckoutAPITests(PaymentsBaseTestCase):
    def test_checkout_creates_order_and_15m_stock_reservation(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            'items': [{'variant_id': self.variant.id, 'quantity': 2}],
            'address_id': self.saved_address.id,
            'payment_method': 'razorpay',
        }

        response = self.client.post(reverse('orders:order_checkout'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('razorpay_order_id', response.data)
        self.assertEqual(response.data['amount'], 319800)  # 1599.00 * 2 * 100 paise
        self.assertIn('reservation_expires_at', response.data)

        # Verify StockReservation created with 15m TTL hold
        order_number = response.data['order_number']
        reservations = StockReservation.objects.filter(order_number=order_number)
        self.assertEqual(reservations.count(), 1)
        res = reservations.first()
        self.assertEqual(res.quantity, 2)
        self.assertEqual(res.status, StockReservation.STATUS_ACTIVE)

        # Verify variant reserved stock incremented
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.reserved_stock, 2)
        self.assertEqual(self.variant.available_stock, 8)

    def test_checkout_insufficient_stock_rejection(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            'items': [{'variant_id': self.variant.id, 'quantity': 15}],  # only 10 available
            'address_id': self.saved_address.id,
            'payment_method': 'razorpay',
        }

        response = self.client.post(reverse('orders:order_checkout'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("available", response.data['error'])

    def test_checkout_cod_disabled_by_default(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            'items': [{'variant_id': self.variant.id, 'quantity': 1}],
            'address_id': self.saved_address.id,
            'payment_method': 'cod',
        }

        response = self.client.post(reverse('orders:order_checkout'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("disabled", response.data['error'].lower())


class RazorpayVerifyAPITests(PaymentsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)

        # Checkout initiation creating order and reservation
        checkout_payload = {
            'items': [{'variant_id': self.variant.id, 'quantity': 2}],
            'address_id': self.saved_address.id,
            'payment_method': 'razorpay',
        }
        res = self.client.post(reverse('orders:order_checkout'), checkout_payload, format='json')
        self.order_id = res.data['order_id']
        self.order_number = res.data['order_number']
        self.rzp_order_id = res.data['razorpay_order_id']
        self.payment_id = "pay_test_capture_12345"

    def test_verify_payment_success_converts_reservation_to_sale(self):
        valid_sig = compute_payment_signature(self.rzp_order_id, self.payment_id)
        verify_payload = {
            'razorpay_order_id': self.rzp_order_id,
            'razorpay_payment_id': self.payment_id,
            'razorpay_signature': valid_sig,
        }

        response = self.client.post(reverse('payments:razorpay_verify'), verify_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['payment_status'], 'Paid')
        self.assertEqual(response.data['order_status'], 'Ordered')

        # Variant stock decremented from 10 to 8, reserved_stock decremented from 2 to 0
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 8)
        self.assertEqual(self.variant.reserved_stock, 0)
        self.assertEqual(self.variant.available_stock, 8)

        # Reservation converted to sale
        reservation = StockReservation.objects.get(order_number=self.order_number)
        self.assertEqual(reservation.status, StockReservation.STATUS_CONVERTED)

        # PaymentTransaction recorded as captured
        txn = PaymentTransaction.objects.get(order__order_number=self.order_number)
        self.assertEqual(txn.status, PaymentTransaction.STATUS_CAPTURED)
        self.assertEqual(txn.gateway_payment_id, self.payment_id)

    def test_verify_payment_tampered_signature_rejected(self):
        verify_payload = {
            'razorpay_order_id': self.rzp_order_id,
            'razorpay_payment_id': self.payment_id,
            'razorpay_signature': 'tampered_signature_string',
        }

        response = self.client.post(reverse('payments:razorpay_verify'), verify_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid", response.data['error'])

        # Stock remains reserved, order remains Pending
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 10)
        self.assertEqual(self.variant.reserved_stock, 2)

    def test_verify_payment_is_strictly_idempotent(self):
        valid_sig = compute_payment_signature(self.rzp_order_id, self.payment_id)
        verify_payload = {
            'razorpay_order_id': self.rzp_order_id,
            'razorpay_payment_id': self.payment_id,
            'razorpay_signature': valid_sig,
        }

        # First verification call
        res1 = self.client.post(reverse('payments:razorpay_verify'), verify_payload, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # Second verification call (duplicate delivery or double-tap)
        res2 = self.client.post(reverse('payments:razorpay_verify'), verify_payload, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)

        # Stock is NOT double-decremented!
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 8)
        self.assertEqual(self.variant.reserved_stock, 0)


class RazorpayWebhookAPITests(PaymentsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            reverse('orders:order_checkout'),
            {'items': [{'variant_id': self.variant.id, 'quantity': 1}], 'address_id': self.saved_address.id},
            format='json',
        )
        self.order_number = res.data['order_number']
        self.rzp_order_id = res.data['razorpay_order_id']
        self.payment_id = "pay_webhook_9999"

    def test_webhook_captured_event_processes_order(self):
        secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', 'placeholder_webhook_secret')
        webhook_body = json.dumps({
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'id': self.payment_id,
                        'order_id': self.rzp_order_id,
                        'amount': 159900,
                        'status': 'captured',
                    }
                }
            }
        }).encode('utf-8')

        valid_sig = hmac.new(secret.encode('utf-8'), webhook_body, hashlib.sha256).hexdigest()

        response = self.client.post(
            reverse('payments:razorpay_webhook'),
            webhook_body,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=valid_sig,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')

        order = Order.objects.get(order_number=self.order_number)
        self.assertEqual(order.payment_status, 'Paid')
        self.assertEqual(order.order_status, 'Ordered')

    def test_webhook_invalid_signature_rejected(self):
        webhook_body = b'{"event": "payment.captured"}'
        response = self.client.post(
            reverse('payments:razorpay_webhook'),
            webhook_body,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='bad_sig',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LatePaymentReconciliationTests(PaymentsBaseTestCase):
    def test_late_payment_with_unreserved_stock_available(self):
        # 1. Customer initiates checkout with 2 units (stock=10, reserved=2)
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            reverse('orders:order_checkout'),
            {'items': [{'variant_id': self.variant.id, 'quantity': 2}], 'address_id': self.saved_address.id},
            format='json',
        )
        order_number = res.data['order_number']
        rzp_order_id = res.data['razorpay_order_id']
        payment_id = "pay_late_unreserved_1"

        # 2. Reservation expires (e.g. 15 minutes elapsed)
        reservation = StockReservation.objects.get(order_number=order_number)
        reservation.expire()

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.reserved_stock, 0)
        self.assertEqual(self.variant.stock, 10)

        # 3. Customer completes late payment
        valid_sig = compute_payment_signature(rzp_order_id, payment_id)
        verify_payload = {
            'razorpay_order_id': rzp_order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': valid_sig,
        }
        verify_res = self.client.post(reverse('payments:razorpay_verify'), verify_payload, format='json')
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)
        self.assertEqual(verify_res.data['payment_status'], 'Paid')
        self.assertEqual(verify_res.data['order_status'], 'Ordered')

        # Stock is allocated from physical stock (10 - 2 = 8)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 8)
        self.assertEqual(self.variant.reserved_stock, 0)

    def test_late_payment_with_depleted_stock_transitions_to_requires_attention(self):
        # 1. Customer initiates checkout for 2 units
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            reverse('orders:order_checkout'),
            {'items': [{'variant_id': self.variant.id, 'quantity': 2}], 'address_id': self.saved_address.id},
            format='json',
        )
        order_number = res.data['order_number']
        rzp_order_id = res.data['razorpay_order_id']
        payment_id = "pay_late_oversold_2"

        # 2. Reservation expires
        reservation = StockReservation.objects.get(order_number=order_number)
        reservation.expire()

        # 3. Meanwhile, all warehouse stock is sold out to other customers (stock=0)
        self.variant.stock = 0
        self.variant.reserved_stock = 0
        self.variant.save(update_fields=['stock', 'reserved_stock'])

        # 4. Customer's late payment comes in!
        valid_sig = compute_payment_signature(rzp_order_id, payment_id)
        verify_payload = {
            'razorpay_order_id': rzp_order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': valid_sig,
        }
        verify_res = self.client.post(reverse('payments:razorpay_verify'), verify_payload, format='json')
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)

        order = Order.objects.get(order_number=order_number)
        # Order enters exceptional state Requires_Attention
        self.assertEqual(order.order_status, 'Requires_Attention')
        self.assertEqual(order.payment_status, 'Paid')

        # Stock is NEVER decremented below zero!
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 0)
        self.assertEqual(self.variant.reserved_stock, 0)

        # Recoverable RefundRecord is created with idempotency key
        refund = RefundRecord.objects.filter(order=order).first()
        self.assertIsNotNone(refund)
        self.assertIn("refund-late-", refund.idempotency_key)
        self.assertEqual(refund.amount, order.total_amount)


class RecoverableRefundCommandTests(PaymentsBaseTestCase):
    def test_command_processes_pending_refund_records(self):
        order = Order.objects.create(
            user=self.user,
            first_name='Kavya',
            phone='9876500000',
            email='kavya@example.com',
            shipping_address='Street 1',
            city='Hyderabad',
            state='Telangana',
            zip_code='500001',
            subtotal=Decimal('1599.00'),
            total_amount=Decimal('1599.00'),
            razorpay_payment_id='pay_test_refund_101',
        )

        RefundRecord.objects.create(
            order=order,
            idempotency_key=f"manual-refund-{order.order_number}",
            amount=order.total_amount,
            status=RefundRecord.STATUS_PENDING,
        )

        call_command('process_pending_refunds')

        refund = RefundRecord.objects.get(order=order)
        self.assertEqual(refund.status, RefundRecord.STATUS_PROCESSED)
        self.assertIsNotNone(refund.razorpay_refund_id)

