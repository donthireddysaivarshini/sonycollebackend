from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from accounts.models import SavedAddress
from catalog.models import ProductVariant
from cart.models import CartItem, StockReservation
from cart.views import get_or_create_cart
from .models import Order, OrderItem, ReturnRequest, ExchangeRequest


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializes immutable order item snapshots.
    Aligns with Section 4.1 of docs/backend/05_API_CONTRACT.md.
    """

    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    product_image = serializers.SerializerMethodField()
    product_slug = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product_name',
            'product_sku',
            'product_slug',
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

    def get_product_slug(self, obj) -> str:
        if obj.product and getattr(obj.product, 'slug', None):
            return obj.product.slug
        if obj.variant and obj.variant.product and getattr(obj.variant.product, 'slug', None):
            return obj.variant.product.slug
        from django.utils.text import slugify
        return slugify(obj.product_name)

    def get_product_image(self, obj) -> str:
        if not obj.product_image:
            return ""
        img = str(obj.product_image).strip()
        if img.startswith('http://') or img.startswith('https://'):
            return img
        if img.startswith('/media/'):
            request = self.context.get('request')
            return request.build_absolute_uri(img) if request else f"http://127.0.0.1:8000{img}"
        clean_img = img.lstrip('/')
        media_url = f"/media/{clean_img}"
        request = self.context.get('request')
        return request.build_absolute_uri(media_url) if request else f"http://127.0.0.1:8000{media_url}"


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
            'coupon_code',
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
    variant_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    sku = serializers.CharField(required=False, allow_blank=True, default='')
    product_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    product_slug = serializers.CharField(required=False, allow_blank=True, default='')
    product_title = serializers.CharField(required=False, allow_blank=True, default='')
    clothing_type = serializers.CharField(required=False, allow_blank=True, default='')
    color = serializers.CharField(required=False, allow_blank=True, default='')
    size = serializers.CharField(required=False, allow_blank=True, default='')
    quantity = serializers.IntegerField(required=True, min_value=1)

    def validate(self, attrs):
        return attrs


class OrderCreateSerializer(serializers.Serializer):
    """
    Validates payload for creating a new order.
    """

    address_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address = serializers.DictField(required=False, allow_null=True)
    payment_method = serializers.CharField(default='razorpay')
    coupon_code = serializers.CharField(required=False, allow_blank=True, default='')
    items = OrderItemCreateInputSerializer(many=True, required=False)

    def validate(self, attrs):
        if not attrs.get('address_id') and not attrs.get('address'):
            raise serializers.ValidationError("Either address_id or address object must be provided.")
        return attrs


class ReturnRequestSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    item_id = serializers.IntegerField(source='item.id', read_only=True)
    product_name = serializers.CharField(source='item.product_name', read_only=True)
    product_sku = serializers.CharField(source='item.product_sku', read_only=True)
    quantity = serializers.IntegerField(source='item.quantity', read_only=True)
    refund_amount = serializers.SerializerMethodField()

    class Meta:
        model = ReturnRequest
        fields = [
            'id',
            'order_number',
            'item_id',
            'product_name',
            'product_sku',
            'quantity',
            'refund_amount',
            'reason',
            'customer_notes',
            'admin_notes',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'status', 'admin_notes', 'created_at', 'updated_at']

    def get_refund_amount(self, obj) -> str:
        return f"{obj.item.line_total:.2f}"


class ReturnRequestCreateSerializer(serializers.Serializer):
    item_id = serializers.IntegerField(required=True)
    reason = serializers.CharField(required=True, max_length=100)
    customer_notes = serializers.CharField(required=False, allow_blank=True, default='')


class ExchangeRequestSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    item_id = serializers.IntegerField(source='item.id', read_only=True)
    original_product_name = serializers.CharField(source='item.product_name', read_only=True)
    original_sku = serializers.CharField(source='item.product_sku', read_only=True)
    product_image = serializers.CharField(source='item.product_image', read_only=True)
    line_total = serializers.SerializerMethodField()
    replacement_variant_id = serializers.IntegerField(source='replacement_variant.id', read_only=True, allow_null=True)
    replacement_sku = serializers.CharField(source='replacement_variant.sku', read_only=True, allow_null=True)
    replacement_details = serializers.SerializerMethodField()
    proof_file_url = serializers.SerializerMethodField()

    class Meta:
        model = ExchangeRequest
        fields = [
            'id',
            'order_number',
            'item_id',
            'original_product_name',
            'original_sku',
            'product_image',
            'line_total',
            'replacement_variant_id',
            'replacement_sku',
            'replacement_details',
            'reason',
            'other_reason',
            'proof_file_url',
            'exchange_code',
            'customer_notes',
            'admin_notes',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'status', 'admin_notes', 'exchange_code', 'created_at', 'updated_at']

    def get_line_total(self, obj) -> str:
        return f"{obj.item.line_total:.2f}"

    def get_replacement_details(self, obj) -> dict:
        v = obj.replacement_variant
        if not v:
            return {}
        return {
            'clothing_type': v.clothing_type,
            'color': v.color.name,
            'size': v.size.name,
            'price': f"{v.final_price:.2f}",
        }

    def get_proof_file_url(self, obj):
        if not obj.proof_file:
            return ''
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.proof_file.url)
        return obj.proof_file.url


class ExchangeRequestCreateSerializer(serializers.Serializer):
    item_id = serializers.IntegerField(required=True)
    reason = serializers.CharField(required=False, default='damaged')
    other_reason = serializers.CharField(required=False, allow_blank=True, default='')
    customer_notes = serializers.CharField(required=False, allow_blank=True, default='')
    replacement_variant_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs.get('reason') == 'other' and not attrs.get('other_reason', '').strip():
            raise serializers.ValidationError({"other_reason": "Please specify the other reason."})
        return attrs


