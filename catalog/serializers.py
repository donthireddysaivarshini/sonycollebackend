from rest_framework import serializers
from .models import (
    Category,
    Color,
    Size,
    Product,
    ProductImage,
    ProductVariant,
    HomepageSection,
    HomepageSectionItem,
    HeroSlide,
)


class CategorySerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    item_count_label = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            'id',
            'name',
            'slug',
            'image',
            'image_url',
            'description',
            'tagline',
            'item_count_label',
        )

    def get_image_url(self, obj):
        if not obj.image:
            return ''
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url

    def get_item_count_label(self, obj):
        if obj.item_count_label and obj.item_count_label.strip():
            return obj.item_count_label.strip()
        count = obj.products.filter(is_active=True).count()
        return f"{count} Signature Styles"


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
    url = serializers.SerializerMethodField()
    color_id = serializers.IntegerField(source='color.id', read_only=True, allow_null=True)
    color_name = serializers.CharField(source='color.name', read_only=True, allow_null=True)
    color_hex = serializers.CharField(source='color.hex_code', read_only=True, allow_null=True)

    class Meta:
        model = ProductImage
        fields = (
            'id',
            'clothing_type',
            'image',
            'url',
            'color',
            'color_id',
            'color_name',
            'color_hex',
            'order',
            'is_primary',
        )

    def get_url(self, obj):
        if not obj.image:
            return ''
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


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
            'is_feeding_collection',
            'is_sarees_collection',
            'is_kidswear_collection',
            'images',
            'variants',
        )


class HeroSlideSerializer(serializers.ModelSerializer):
    desktop_image_url = serializers.SerializerMethodField()
    mobile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = HeroSlide
        fields = (
            'id',
            'title',
            'desktop_image',
            'desktop_image_url',
            'mobile_image',
            'mobile_image_url',
            'cta_link',
            'preserve_artwork',
            'display_order',
        )

    def get_desktop_image_url(self, obj):
        if not obj.desktop_image:
            return ''
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.desktop_image.url)
        return obj.desktop_image.url

    def get_mobile_image_url(self, obj):
        img = obj.mobile_image or obj.desktop_image
        if not img:
            return ''
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(img.url)
        return img.url


class HomepageSectionSerializer(serializers.ModelSerializer):
    """
    Serializes a HomepageSection with its assigned active products
    ordered by merchandising sequence.
    """

    products = serializers.SerializerMethodField()

    class Meta:
        model = HomepageSection
        fields = (
            'id',
            'title',
            'slug',
            'subtitle',
            'badge_label',
            'view_all_link',
            'direction',
            'display_order',
            'products',
        )

    def get_products(self, obj):
        items = (
            obj.items.filter(product__is_active=True)
            .select_related('product__category')
            .prefetch_related('product__images', 'product__variants__color', 'product__variants__size')
            .order_by('order', 'id')
        )
        products = [item.product for item in items]
        return ProductSerializer(products, many=True, context=self.context).data


