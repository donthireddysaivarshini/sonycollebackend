from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from accounts.models import SavedAddress
from catalog.models import ProductVariant
from cart.models import CartItem, StockReservation
from cart.views import get_or_create_cart
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializes immutable order item snapshots.
    Aligns with Section 4.1 of docs/backend/05_API_CONTRACT.md.
    """

    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product_name',
            'product_sku',
            'product_image',
            'clothing_type',
            'color',
            'size',
            'unit_price',
            'quantity',
            'line_total',
        ]

    def get_unit_price(self, obj) -> str:
        return f"{obj.unit_price:.2f}"

    def get_line_total(self, obj) -> str:
        return f"{obj.line_total:.2f}"


class OrderSerializer(serializers.ModelSerializer):
    """
    Detailed serialization of a customer order including line items
    and shipping information.
    """

    items = OrderItemSerializer(many=True, read_only=True)
    total_amount = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    shipping_fee = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    is_cancellable = serializers.BooleanField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'created_at',
            'order_status',
            'payment_status',
            'payment_method',
            'total_amount',
            'subtotal',
            'shipping_fee',
            'discount',
            'is_cancellable',
            'tracking_number',
            'carrier_name',
            'shipping_address',
            'apartment',
            'landmark',
            'city',
            'state',
            'zip_code',
            'first_name',
            'last_name',
            'phone',
            'email',
            'items',
        ]

    def get_total_amount(self, obj) -> str:
        return f"{obj.total_amount:.2f}"

    def get_subtotal(self, obj) -> str:
        return f"{obj.subtotal:.2f}"

    def get_shipping_fee(self, obj) -> str:
        return f"{obj.shipping_fee:.2f}"

    def get_discount(self, obj) -> str:
        return f"{obj.discount:.2f}"


class OrderItemCreateInputSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(required=True, min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    """
    Validates payload for creating a new order.
    """

    address_id = serializers.IntegerField(required=False, allow_null=True)
    address = serializers.DictField(required=False, allow_null=True)
    payment_method = serializers.ChoiceField(
        choices=['razorpay', 'cod'],
        default='razorpay',
    )
    items = OrderItemCreateInputSerializer(many=True, required=False)

    def validate(self, attrs):
        if not attrs.get('address_id') and not attrs.get('address'):
            raise serializers.ValidationError("Either address_id or address object must be provided.")
        return attrs

