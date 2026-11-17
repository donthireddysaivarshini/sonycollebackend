from decimal import Decimal

from rest_framework import serializers

from accounts.models import SavedAddress
from catalog.models import ProductVariant
from .models import Cart, CartItem, StockReservation


class CartItemSerializer(serializers.ModelSerializer):
    """
    Detailed serialization of a cart item with enriched product & variant metadata.
    """

    variant_id = serializers.IntegerField(source='variant.id', read_only=True)
    product_id = serializers.IntegerField(source='variant.product.id', read_only=True)
    product_title = serializers.CharField(source='variant.product.title', read_only=True)
    product_slug = serializers.CharField(source='variant.product.slug', read_only=True)
    product_image = serializers.SerializerMethodField()
    clothing_type = serializers.CharField(source='variant.clothing_type', read_only=True)
    color = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()
    sku = serializers.CharField(source='variant.sku', read_only=True)
    unit_price = serializers.SerializerMethodField()
    original_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    available_stock = serializers.IntegerField(read_only=True)
    in_stock = serializers.BooleanField(source='is_available', read_only=True)

    class Meta:
        model = CartItem
        fields = [
            'id',
            'variant_id',
            'product_id',
            'product_title',
            'product_slug',
            'product_image',
            'clothing_type',
            'color',
            'size',
            'sku',
            'unit_price',
            'original_price',
            'quantity',
            'line_total',
            'available_stock',
            'in_stock',
        ]

    def get_product_image(self, obj) -> str:
        first_img = obj.variant.product.images.first()
        return first_img.image if first_img else ''

    def get_color(self, obj) -> dict:
        color = obj.variant.color
        return {
            'id': color.id,
            'name': color.name,
            'hex_code': color.hex_code,
        }

    def get_size(self, obj) -> dict:
        size = obj.variant.size
        return {
            'id': size.id,
            'name': size.name,
        }

    def get_unit_price(self, obj) -> str:
        return f"{obj.unit_price:.2f}"

    def get_original_price(self, obj) -> str | None:
        mrp = obj.variant.product.mrp
        return f"{mrp:.2f}" if mrp else None

    def get_line_total(self, obj) -> str:
        return f"{obj.line_total:.2f}"


class CartSerializer(serializers.ModelSerializer):
    """
    Authoritative representation of the shopping cart.
    Calculates subtotal, shipping_fee, tax, and grand_total server-side.
    """

    items = CartItemSerializer(many=True, read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    subtotal = serializers.SerializerMethodField()
    shipping_fee = serializers.SerializerMethodField()
    tax_amount = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            'id',
            'session_key',
            'items',
            'items_count',
            'subtotal',
            'shipping_fee',
            'tax_amount',
            'grand_total',
        ]

    def get_subtotal(self, obj) -> str:
        return f"{obj.subtotal:.2f}"

    def get_shipping_fee(self, obj) -> str:
        return f"{obj.shipping_fee:.2f}"

    def get_tax_amount(self, obj) -> str:
        return f"{obj.tax_amount:.2f}"

    def get_grand_total(self, obj) -> str:
        return f"{obj.grand_total:.2f}"


class CartItemAddSerializer(serializers.Serializer):
    """
    Validates adding an item to the shopping cart.
    """

    variant_id = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(required=False, default=1, min_value=1)

    def validate_variant_id(self, value):
        # Expire stale holds first to obtain live available stock
        StockReservation.expire_stale_reservations(variant_id=value)
        try:
            variant = ProductVariant.objects.select_related('product').get(id=value)
        except ProductVariant.DoesNotExist:
            raise serializers.ValidationError("Product variant does not exist.")

        if not variant.product.is_active:
            raise serializers.ValidationError("This product is currently unavailable.")

        if variant.available_stock <= 0:
            raise serializers.ValidationError("This variant is currently out of stock.")

        return value

    def validate(self, attrs):
        variant = ProductVariant.objects.get(id=attrs['variant_id'])
        requested_qty = attrs.get('quantity', 1)

        # Check against available stock
        if requested_qty > variant.available_stock:
            raise serializers.ValidationError({
                'quantity': f"Only {variant.available_stock} unit(s) available for selected variant."
            })

        attrs['variant_obj'] = variant
        return attrs


class CartItemUpdateSerializer(serializers.Serializer):
    """
    Validates modifying the quantity of an existing cart item.
    """

    quantity = serializers.IntegerField(required=True, min_value=1)


class CartValidateItemInputSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(required=True, min_value=1)


class CartValidateRequestSerializer(serializers.Serializer):
    """
    Input serializer for POST /api/cart/validate/
    """

    items = CartValidateItemInputSerializer(many=True, required=True)


class CartMergeSerializer(serializers.Serializer):
    """
    Input serializer for POST /api/cart/merge/
    """

    session_key = serializers.CharField(required=True, max_length=100)


class DeliveryAddressInputSerializer(serializers.Serializer):
    """
    Validates delivery address submitted during checkout preview.
    Supports both camelCase and snake_case representations.
    """

    fullName = serializers.CharField(required=False, max_length=150)
    full_name = serializers.CharField(required=False, max_length=150)
    phone = serializers.CharField(required=True, max_length=20)
    houseFlat = serializers.CharField(required=False, max_length=255)
    house_flat = serializers.CharField(required=False, max_length=255)
    streetArea = serializers.CharField(required=False, max_length=255)
    street_area = serializers.CharField(required=False, max_length=255)
    landmark = serializers.CharField(required=False, allow_blank=True, default='')
    city = serializers.CharField(required=True, max_length=100)
    state = serializers.CharField(required=True, max_length=100)
    pincode = serializers.CharField(required=False, max_length=10)
    zip_code = serializers.CharField(required=False, max_length=10)

    def validate(self, attrs):
        name = attrs.get('fullName') or attrs.get('full_name')
        if not name:
            raise serializers.ValidationError({'fullName': "Full name is required."})

        house = attrs.get('houseFlat') or attrs.get('house_flat')
        if not house:
            raise serializers.ValidationError({'houseFlat': "Flat / House / Building details are required."})

        street = attrs.get('streetArea') or attrs.get('street_area')
        if not street:
            raise serializers.ValidationError({'streetArea': "Street / Colony / Area details are required."})

        pin = attrs.get('pincode') or attrs.get('zip_code')
        if not pin or len(pin.strip()) != 6 or not pin.strip().isdigit():
            raise serializers.ValidationError({'pincode': "A valid 6-digit postal PIN code is required."})

        attrs['normalized_full_name'] = name.strip()
        attrs['normalized_house_flat'] = house.strip()
        attrs['normalized_street_area'] = street.strip()
        attrs['normalized_pincode'] = pin.strip()
        return attrs


class CheckoutSummaryRequestSerializer(serializers.Serializer):
    """
    Validates payload for POST /api/cart/checkout-summary/
    """

    address_id = serializers.IntegerField(required=False, allow_null=True)
    address = DeliveryAddressInputSerializer(required=False, allow_null=True)
    items = CartValidateItemInputSerializer(many=True, required=False)

    def validate(self, attrs):
        if not attrs.get('address_id') and not attrs.get('address'):
            raise serializers.ValidationError(
                "Either 'address_id' of a saved address or inline 'address' object must be provided."
            )
        return attrs

