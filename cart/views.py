import uuid
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import SavedAddress
from catalog.models import ProductVariant
from .models import Cart, CartItem, StockReservation
from .serializers import (
    CartItemAddSerializer,
    CartItemSerializer,
    CartItemUpdateSerializer,
    CartMergeSerializer,
    CartSerializer,
    CartValidateRequestSerializer,
    CheckoutSummaryRequestSerializer,
)


def get_or_create_cart(request) -> tuple[Cart, str | None]:
    """
    Resolves or creates the appropriate shopping cart.
    1. If customer is authenticated: binds to request.user.
    2. If guest visitor: binds to session key passed in 'X-Session-Key' header,
       query parameter, or Django session.
    """
    session_key = (
        request.headers.get('X-Session-Key')
        or request.query_params.get('session_key')
        or (request.session.session_key if hasattr(request, 'session') and request.session.session_key else None)
    )

    if request.user and request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart, session_key

    if not session_key:
        session_key = str(uuid.uuid4())

    cart, _ = Cart.objects.get_or_create(session_key=session_key, user=None)
    return cart, session_key


class CartView(APIView):
    """
    Retrieve active shopping cart with all items and authoritative server-side totals.
    GET /api/cart/
    """

    permission_classes = [AllowAny]

    def get(self, request):
        StockReservation.expire_stale_reservations()
        cart, session_key = get_or_create_cart(request)
        serializer = CartSerializer(cart)
        response = Response(serializer.data, status=status.HTTP_200_OK)
        if session_key and not request.user.is_authenticated:
            response['X-Session-Key'] = session_key
        return response


class CartItemCreateView(APIView):
    """
    Add a product variant to the customer's active cart.
    POST /api/cart/items/
    Body: {"variant_id": 101, "quantity": 1}
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CartItemAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        variant = serializer.validated_data['variant_obj']
        requested_qty = serializer.validated_data.get('quantity', 1)

        with transaction.atomic():
            cart, session_key = get_or_create_cart(request)
            existing_item = CartItem.objects.filter(cart=cart, variant=variant).first()

            if existing_item:
                new_qty = existing_item.quantity + requested_qty
                if new_qty > variant.available_stock:
                    return Response(
                        {
                            'quantity': [
                                f"Cannot add {requested_qty} more. Total in cart ({new_qty}) exceeds available stock ({variant.available_stock})."
                            ]
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                existing_item.quantity = new_qty
                existing_item.save(update_fields=['quantity', 'updated_at'])
            else:
                CartItem.objects.create(
                    cart=cart,
                    variant=variant,
                    quantity=requested_qty,
                )

        response_serializer = CartSerializer(cart)
        response = Response(response_serializer.data, status=status.HTTP_201_CREATED)
        if session_key and not request.user.is_authenticated:
            response['X-Session-Key'] = session_key
        return response


class CartItemDetailView(APIView):
    """
    Update item quantity or remove item from shopping cart.
    PATCH /api/cart/items/<id>/
    DELETE /api/cart/items/<id>/
    """

    permission_classes = [AllowAny]

    def patch(self, request, item_id):
        serializer = CartItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_quantity = serializer.validated_data['quantity']

        cart, session_key = get_or_create_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)

        StockReservation.expire_stale_reservations(variant_id=item.variant_id)
        if new_quantity > item.variant.available_stock:
            return Response(
                {
                    'quantity': [
                        f"Requested quantity ({new_quantity}) exceeds available stock ({item.variant.available_stock})."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        item.quantity = new_quantity
        item.save(update_fields=['quantity', 'updated_at'])

        response = Response(CartSerializer(cart).data, status=status.HTTP_200_OK)
        if session_key and not request.user.is_authenticated:
            response['X-Session-Key'] = session_key
        return response

    def delete(self, request, item_id):
        cart, session_key = get_or_create_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.delete()

        response = Response(CartSerializer(cart).data, status=status.HTTP_200_OK)
        if session_key and not request.user.is_authenticated:
            response['X-Session-Key'] = session_key
        return response


class CartClearView(APIView):
    """
    Remove all items from the current cart.
    POST /api/cart/clear/
    """

    permission_classes = [AllowAny]

    def post(self, request):
        cart, session_key = get_or_create_cart(request)
        cart.clear()

        response = Response(CartSerializer(cart).data, status=status.HTTP_200_OK)
        if session_key and not request.user.is_authenticated:
            response['X-Session-Key'] = session_key
        return response


class CartMergeView(APIView):
    """
    Merge a guest session cart into an authenticated customer's cart upon login.
    POST /api/cart/merge/
    Body: {"session_key": "guest-uuid"}
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CartMergeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        guest_session_key = serializer.validated_data['session_key']

        user_cart, _ = Cart.objects.get_or_create(user=request.user)
        guest_cart = Cart.objects.filter(session_key=guest_session_key, user=None).first()

        if guest_cart and guest_cart.items.exists():
            with transaction.atomic():
                for guest_item in guest_cart.items.select_related('variant', 'variant__product'):
                    variant = guest_item.variant
                    if not variant.product.is_active or variant.available_stock <= 0:
                        continue

                    user_item = CartItem.objects.filter(cart=user_cart, variant=variant).first()
                    if user_item:
                        merged_qty = min(user_item.quantity + guest_item.quantity, variant.available_stock)
                        user_item.quantity = merged_qty
                        user_item.save(update_fields=['quantity', 'updated_at'])
                    else:
                        CartItem.objects.create(
                            cart=user_cart,
                            variant=variant,
                            quantity=min(guest_item.quantity, variant.available_stock),
                        )

                # Clean up guest cart once merged
                guest_cart.delete()

        return Response(CartSerializer(user_cart).data, status=status.HTTP_200_OK)


class CartValidateView(APIView):
    """
    Real-time pre-checkout stock & pricing validation.
    POST /api/cart/validate/
    Aligns strictly with Section 3.1 of docs/backend/05_API_CONTRACT.md.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CartValidateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items_payload = serializer.validated_data['items']

        # Expire stale reservations first to guarantee live accuracy
        StockReservation.expire_stale_reservations()

        errors = []
        valid_items = []
        subtotal = Decimal('0.00')

        for item_data in items_payload:
            v_id = item_data['variant_id']
            qty = item_data['quantity']

            try:
                variant = ProductVariant.objects.select_related('product').get(id=v_id)
            except ProductVariant.DoesNotExist:
                errors.append({
                    'variant_id': v_id,
                    'error': f"Variant ID {v_id} does not exist.",
                })
                continue

            if not variant.product.is_active:
                errors.append({
                    'variant_id': v_id,
                    'error': f"Product '{variant.product.title}' is currently unavailable.",
                })
                continue

            avail = variant.available_stock
            if avail < qty:
                errors.append({
                    'variant_id': v_id,
                    'error': f"Only {avail} unit(s) available for selected variant.",
                })
            else:
                unit_price = variant.final_price
                line_total = unit_price * qty
                subtotal += line_total
                valid_items.append({
                    'variant_id': v_id,
                    'available_stock': avail,
                    'unit_price': f"{unit_price:.2f}",
                })

        if errors:
            return Response(
                {
                    'is_valid': False,
                    'errors': errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        shipping_fee = Decimal('0.00')
        grand_total = subtotal + shipping_fee

        return Response(
            {
                'is_valid': True,
                'subtotal': f"{subtotal:.2f}",
                'shipping_fee': f"{shipping_fee:.2f}",
                'total': f"{grand_total:.2f}",
                'items': valid_items,
            },
            status=status.HTTP_200_OK,
        )


class CheckoutSummaryView(APIView):
    """
    Authoritative financial and delivery address calculation prior to order placement.
    POST /api/cart/checkout-summary/
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CheckoutSummaryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        StockReservation.expire_stale_reservations()

        # Resolve items either from explicit payload or active cart
        items_payload = validated_data.get('items')
        resolved_items = []
        if items_payload:
            for itm in items_payload:
                try:
                    variant = ProductVariant.objects.select_related('product', 'color', 'size').get(id=itm['variant_id'])
                except ProductVariant.DoesNotExist:
                    return Response(
                        {'error': f"Variant ID {itm['variant_id']} does not exist."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                resolved_items.append({'variant': variant, 'quantity': itm['quantity']})
        else:
            cart, _ = get_or_create_cart(request)
            if not cart.items.exists():
                return Response(
                    {'error': "Shopping cart is empty."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for itm in cart.items.select_related('variant', 'variant__product', 'variant__color', 'variant__size'):
                resolved_items.append({'variant': itm.variant, 'quantity': itm.quantity})

        # Validate inventory
        subtotal = Decimal('0.00')
        items_detail = []
        for entry in resolved_items:
            variant = entry['variant']
            qty = entry['quantity']
            if not variant.product.is_active:
                return Response(
                    {'error': f"Product '{variant.product.title}' is currently inactive."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if variant.available_stock < qty:
                return Response(
                    {'error': f"Only {variant.available_stock} unit(s) available for {variant.product.title} ({variant.sku})."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            unit_price = variant.final_price
            line_total = unit_price * qty
            subtotal += line_total
            items_detail.append({
                'variant_id': variant.id,
                'sku': variant.sku,
                'product_title': variant.product.title,
                'clothing_type': variant.clothing_type,
                'color': variant.color.name,
                'size': variant.size.name,
                'unit_price': f"{unit_price:.2f}",
                'quantity': qty,
                'line_total': f"{line_total:.2f}",
            })

        # Resolve delivery address
        address_id = validated_data.get('address_id')
        address_obj = validated_data.get('address')
        resolved_address = {}

        if address_id:
            if request.user.is_authenticated:
                saved = SavedAddress.objects.filter(id=address_id, user=request.user).first()
                if not saved:
                    return Response(
                        {'error': f"Saved address #{address_id} not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                resolved_address = {
                    'id': saved.id,
                    'fullName': saved.recipient_name,
                    'phone': saved.phone,
                    'houseFlat': saved.address_line1,
                    'streetArea': saved.address_line2,
                    'landmark': saved.landmark or '',
                    'city': saved.city,
                    'state': saved.state,
                    'pincode': saved.pincode,
                }
            else:
                return Response(
                    {'error': "Authentication required to use saved address ID."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        elif address_obj:
            resolved_address = {
                'fullName': address_obj['normalized_full_name'],
                'phone': address_obj['phone'],
                'houseFlat': address_obj['normalized_house_flat'],
                'streetArea': address_obj['normalized_street_area'],
                'landmark': address_obj.get('landmark', ''),
                'city': address_obj['city'],
                'state': address_obj['state'],
                'pincode': address_obj['normalized_pincode'],
            }

        shipping_fee = Decimal('0.00')
        tax_amount = Decimal('0.00')
        grand_total = subtotal + shipping_fee + tax_amount

        return Response(
            {
                'subtotal': f"{subtotal:.2f}",
                'shipping_fee': f"{shipping_fee:.2f}",
                'tax_amount': f"{tax_amount:.2f}",
                'grand_total': f"{grand_total:.2f}",
                'items_count': sum(e['quantity'] for e in resolved_items),
                'items': items_detail,
                'delivery_address': resolved_address,
            },
            status=status.HTTP_200_OK,
        )

