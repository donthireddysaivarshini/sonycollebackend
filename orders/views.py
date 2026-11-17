from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import SavedAddress
from catalog.models import ProductVariant
from cart.models import Cart, CartItem, StockReservation
from .models import Order, OrderItem
from .serializers import OrderCreateSerializer, OrderSerializer


class OrderListView(generics.ListAPIView):
    """
    Retrieve customer order history.
    GET /api/orders/
    Aligns with Section 4.1 of docs/backend/05_API_CONTRACT.md.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related('items')
            .order_by('-created_at')
        )


class OrderDetailView(generics.RetrieveAPIView):
    """
    Retrieve single order by its public secure order_number (e.g., SFK-2611-KJ7M).
    GET /api/orders/<order_number>/
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    lookup_field = 'order_number'

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related('items')
        )


class OrderCancelView(APIView):
    """
    Cancel a pending or processing customer order prior to warehouse dispatch.
    POST /api/orders/<order_number>/cancel/
    Aligns with Section 4.2 of docs/backend/05_API_CONTRACT.md.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number, user=request.user)

        if not order.is_cancellable:
            return Response(
                {'error': "This order has already shipped and can no longer be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Release any active stock reservations linked to this order
            StockReservation.objects.filter(
                order_number=order.order_number,
                status=StockReservation.STATUS_ACTIVE,
            ).update(status=StockReservation.STATUS_RELEASED)

            order.order_status = 'Cancelled'
            order.save(update_fields=['order_status', 'updated_at'])

        return Response(
            {
                'message': "Order cancelled successfully.",
                'order_status': "Cancelled",
            },
            status=status.HTTP_200_OK,
        )


class OrderCreateView(APIView):
    """
    Create a new customer order from cart or explicit item payload.
    Captures immutable snapshots of product name, variant, and pricing.
    POST /api/orders/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        user = request.user

        # Resolve delivery address
        address_id = validated_data.get('address_id')
        address_obj = validated_data.get('address')

        if address_id:
            saved_addr = get_object_or_404(SavedAddress, id=address_id, user=user)
            first_name = saved_addr.recipient_name.split()[0] if saved_addr.recipient_name else user.first_name
            last_name = " ".join(saved_addr.recipient_name.split()[1:]) if saved_addr.recipient_name and len(saved_addr.recipient_name.split()) > 1 else user.last_name
            phone = saved_addr.phone
            shipping_address = saved_addr.address_line1
            apartment = saved_addr.address_line2
            landmark = saved_addr.landmark or ''
            city = saved_addr.city
            state = saved_addr.state
            zip_code = saved_addr.pincode
        else:
            full_name = address_obj.get('fullName') or address_obj.get('full_name') or user.get_full_name()
            first_name = full_name.split()[0] if full_name else user.first_name
            last_name = " ".join(full_name.split()[1:]) if full_name and len(full_name.split()) > 1 else user.last_name
            phone = address_obj.get('phone', user.phone or '')
            shipping_address = address_obj.get('houseFlat') or address_obj.get('house_flat') or address_obj.get('address', '')
            apartment = address_obj.get('streetArea') or address_obj.get('street_area') or address_obj.get('apartment', '')
            landmark = address_obj.get('landmark', '')
            city = address_obj.get('city', '')
            state = address_obj.get('state', '')
            zip_code = address_obj.get('pincode') or address_obj.get('zip_code', '')

        # Resolve items
        items_payload = validated_data.get('items')
        resolved_items = []
        user_cart = None

        if items_payload:
            for itm in items_payload:
                variant = get_object_or_404(
                    ProductVariant.objects.select_related('product', 'color', 'size'),
                    id=itm['variant_id'],
                )
                if not variant.product.is_active or variant.available_stock < itm['quantity']:
                    return Response(
                        {'error': f"Only {variant.available_stock} unit(s) available for {variant.sku}."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                resolved_items.append({'variant': variant, 'quantity': itm['quantity']})
        else:
            user_cart = Cart.objects.filter(user=user).first()
            if not user_cart or not user_cart.items.exists():
                return Response({'error': "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

            for cart_item in user_cart.items.select_related('variant', 'variant__product', 'variant__color', 'variant__size'):
                variant = cart_item.variant
                if not variant.product.is_active or variant.available_stock < cart_item.quantity:
                    return Response(
                        {'error': f"Only {variant.available_stock} unit(s) available for {variant.sku}."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                resolved_items.append({'variant': variant, 'quantity': cart_item.quantity})

        subtotal = sum((entry['variant'].final_price * entry['quantity'] for entry in resolved_items), Decimal('0.00'))
        shipping_fee = Decimal('0.00')
        discount = Decimal('0.00')
        total_amount = subtotal + shipping_fee - discount

        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=user.email,
                shipping_address=shipping_address,
                apartment=apartment,
                landmark=landmark,
                city=city,
                state=state,
                zip_code=zip_code,
                subtotal=subtotal,
                discount=discount,
                shipping_fee=shipping_fee,
                total_amount=total_amount,
                payment_method=validated_data.get('payment_method', 'razorpay'),
                payment_status='Pending',
                order_status='Ordered',
            )

            # Create snapshot OrderItem rows
            for entry in resolved_items:
                v = entry['variant']
                q = entry['quantity']
                first_img = v.product.images.first()
                img_url = first_img.image if first_img else ''

                OrderItem.objects.create(
                    order=order,
                    product=v.product,
                    variant=v,
                    product_name=v.product.title,
                    product_sku=v.sku,
                    product_image=img_url,
                    clothing_type=v.clothing_type,
                    color=v.color.name,
                    size=v.size.name,
                    unit_price=v.final_price,
                    quantity=q,
                    line_total=v.final_price * q,
                )

            # Clear cart if order originated from user's active cart
            if user_cart:
                user_cart.clear()

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderCheckoutView(APIView):
    """
    Initiate checkout: validates inventory, locks variants, establishes 15m StockReservation,
    creates Order & OrderItem snapshots, and initializes Razorpay online order.
    POST /api/orders/checkout/
    Aligns with Section 3.2 of docs/backend/05_API_CONTRACT.md.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.conf import settings
        from payments.models import PaymentTransaction
        from payments.razorpay_client import create_razorpay_order

        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        user = request.user
        payment_method = validated_data.get('payment_method', 'razorpay')

        # Check COD policy
        if payment_method == 'cod' and not getattr(settings, 'COD_ENABLED', False):
            return Response(
                {'error': "Cash on Delivery is currently disabled pending policy confirmation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve delivery address
        address_id = validated_data.get('address_id')
        address_obj = validated_data.get('address')

        if address_id:
            saved_addr = get_object_or_404(SavedAddress, id=address_id, user=user)
            first_name = saved_addr.recipient_name.split()[0] if saved_addr.recipient_name else user.first_name
            last_name = " ".join(saved_addr.recipient_name.split()[1:]) if saved_addr.recipient_name and len(saved_addr.recipient_name.split()) > 1 else user.last_name
            phone = saved_addr.phone
            shipping_address = saved_addr.address_line1
            apartment = saved_addr.address_line2
            landmark = saved_addr.landmark or ''
            city = saved_addr.city
            state = saved_addr.state
            zip_code = saved_addr.pincode
        else:
            full_name = address_obj.get('fullName') or address_obj.get('full_name') or user.get_full_name()
            first_name = full_name.split()[0] if full_name else user.first_name
            last_name = " ".join(full_name.split()[1:]) if full_name and len(full_name.split()) > 1 else user.last_name
            phone = address_obj.get('phone', user.phone or '')
            shipping_address = address_obj.get('houseFlat') or address_obj.get('house_flat') or address_obj.get('address', '')
            apartment = address_obj.get('streetArea') or address_obj.get('street_area') or address_obj.get('apartment', '')
            landmark = address_obj.get('landmark', '')
            city = address_obj.get('city', '')
            state = address_obj.get('state', '')
            zip_code = address_obj.get('pincode') or address_obj.get('zip_code', '')

        # Resolve items
        items_payload = validated_data.get('items')
        resolved_items = []
        user_cart = None

        if items_payload:
            for itm in items_payload:
                try:
                    variant = ProductVariant.objects.select_related('product', 'color', 'size').get(id=itm['variant_id'])
                except ProductVariant.DoesNotExist:
                    return Response({'error': f"Variant ID {itm['variant_id']} not found."}, status=status.HTTP_400_BAD_REQUEST)
                resolved_items.append({'variant': variant, 'quantity': itm['quantity']})
        else:
            user_cart = Cart.objects.filter(user=user).first()
            if not user_cart or not user_cart.items.exists():
                return Response({'error': "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

            for cart_item in user_cart.items.select_related('variant', 'variant__product', 'variant__color', 'variant__size'):
                resolved_items.append({'variant': cart_item.variant, 'quantity': cart_item.quantity})

        subtotal = sum((entry['variant'].final_price * entry['quantity'] for entry in resolved_items), Decimal('0.00'))
        shipping_fee = Decimal('0.00')
        discount = Decimal('0.00')
        total_amount = subtotal + shipping_fee - discount

        with transaction.atomic():
            # Validate available stock under row lock
            for entry in resolved_items:
                v = ProductVariant.objects.select_for_update().get(id=entry['variant'].id)
                q = entry['quantity']
                if not v.product.is_active or v.available_stock < q:
                    return Response(
                        {'error': f"Only {v.available_stock} item(s) available for selected variant."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                entry['variant'] = v

            order = Order.objects.create(
                user=user,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=user.email,
                shipping_address=shipping_address,
                apartment=apartment,
                landmark=landmark,
                city=city,
                state=state,
                zip_code=zip_code,
                subtotal=subtotal,
                discount=discount,
                shipping_fee=shipping_fee,
                total_amount=total_amount,
                payment_method=payment_method,
                payment_status='Pending',
                order_status='Ordered',
            )

            # Create immutable OrderItem snapshots
            for entry in resolved_items:
                v = entry['variant']
                q = entry['quantity']
                first_img = v.product.images.first()
                img_url = first_img.image if first_img else ''

                OrderItem.objects.create(
                    order=order,
                    product=v.product,
                    variant=v,
                    product_name=v.product.title,
                    product_sku=v.sku,
                    product_image=img_url,
                    clothing_type=v.clothing_type,
                    color=v.color.name,
                    size=v.size.name,
                    unit_price=v.final_price,
                    quantity=q,
                    line_total=v.final_price * q,
                )

            # Clear cart
            if user_cart:
                user_cart.clear()

            # Handle Online Razorpay checkout
            if payment_method == 'razorpay':
                created_reservations = []
                for entry in resolved_items:
                    res = StockReservation.create_reservation(
                        variant=entry['variant'],
                        quantity=entry['quantity'],
                        user=user,
                        order_number=order.order_number,
                        ttl_minutes=15,
                    )
                    res.order = order
                    res.save(update_fields=['order'])
                    created_reservations.append(res)

                amount_paise = int(total_amount * 100)
                rzp_order = create_razorpay_order(amount_paise=amount_paise, receipt=order.order_number)
                rzp_order_id = rzp_order['id']

                order.razorpay_order_id = rzp_order_id
                order.save(update_fields=['razorpay_order_id', 'updated_at'])

                PaymentTransaction.objects.create(
                    order=order,
                    gateway='razorpay',
                    gateway_order_id=rzp_order_id,
                    amount=total_amount,
                    status=PaymentTransaction.STATUS_INITIATED,
                    raw_response=rzp_order,
                )

                expires_at_iso = created_reservations[0].expires_at.isoformat() if created_reservations else ''

                return Response(
                    {
                        'order_id': order.id,
                        'order_number': order.order_number,
                        'payment_method': 'razorpay',
                        'razorpay_order_id': rzp_order_id,
                        'amount': amount_paise,
                        'currency': 'INR',
                        'key': getattr(settings, 'RAZORPAY_KEY_ID', 'rzp_test_placeholder_key'),
                        'reservation_expires_at': expires_at_iso,
                    },
                    status=status.HTTP_201_CREATED,
                )

            # Handle COD checkout (if enabled)
            for entry in resolved_items:
                ProductVariant.objects.filter(id=entry['variant'].id).update(stock=F('stock') - entry['quantity'])

            return Response(
                {
                    'order_id': order.id,
                    'order_number': order.order_number,
                    'payment_method': 'cod',
                    'order_status': order.order_status,
                    'payment_status': order.payment_status,
                    'total_amount': f"{order.total_amount:.2f}",
                },
                status=status.HTTP_201_CREATED,
            )


