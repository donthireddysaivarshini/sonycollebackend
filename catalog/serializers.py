from rest_framework import serializers
from .models import Category, Color, Size, Product, ProductImage, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = (
            'id',
            'name',
            'slug',
            'image',
            'description',
            'tagline',
            'item_count_label',
        )


class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = ('id', 'name', 'hex_code')


class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = ('id', 'name')


class ProductVariantSerializer(serializers.ModelSerializer):
    color = ColorSerializer(read_only=True)
    size = SizeSerializer(read_only=True)
    clothing_type = serializers.SerializerMethodField()
    final_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    available_stock = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProductVariant
        fields = (
            'id',
            'clothing_type',
            'color',
            'size',
            'sku',
            'stock',
            'available_stock',
            'price_override',
            'final_price',
        )

    def get_clothing_type(self, obj):
        # Format as 'feeding', 'non_feeding', or 'standard' to match frontend DTO
        if obj.clothing_type == 'Feeding':
            return 'feeding'
        elif obj.clothing_type == 'Non-Feeding':
            return 'non_feeding'
        return 'standard'


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ('id', 'image', 'order', 'is_primary')


class CategoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug')


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializes Product to match the DjangoProductResponse DTO expected by
    sony-feeding-kurtis-frontend (mapDjangoProduct).
    """

    sku = serializers.CharField(source='sku_prefix', read_only=True)
    category = CategoryBriefSerializer(read_only=True)
    original_price = serializers.DecimalField(
        source='mrp',
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    discount_percentage = serializers.IntegerField(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            'id',
            'title',
            'slug',
            'sku',
            'category',
            'feeding_config',
            'price',
            'original_price',
            'mrp',
            'discount_percentage',
            'rating',
            'review_count',
            'description',
            'fabric',
            'care_instructions',
            'is_new_arrival',
            'is_best_seller',
            'is_handstock',
            'images',
            'variants',
        )
