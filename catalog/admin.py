from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Color, Size, Product, ProductImage, ProductVariant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'slug',
        'item_count_label',
        'display_order',
        'is_active',
        'created_at',
    )
    list_editable = ('display_order', 'is_active')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('display_order', 'name')


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ('name', 'hex_code', 'color_preview')
    search_fields = ('name', 'hex_code')

    def color_preview(self, obj):
        return format_html(
            '<div style="width:24px; height:24px; background-color:{}; border:1px solid #ccc; border-radius:4px;"></div>',
            obj.hex_code,
        )

    color_preview.short_description = 'Swatch'


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    list_editable = ('order',)
    ordering = ('order', 'name')


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'order', 'is_primary')


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = (
        'clothing_type',
        'color',
        'size',
        'sku',
        'stock',
        'reserved_stock',
        'price_override',
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'category',
        'feeding_config',
        'price',
        'mrp',
        'is_new_arrival',
        'is_best_seller',
        'is_handstock',
        'is_active',
    )
    list_filter = (
        'category',
        'feeding_config',
        'is_new_arrival',
        'is_best_seller',
        'is_handstock',
        'is_active',
    )
    search_fields = ('title', 'sku_prefix', 'description', 'fabric')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ProductImageInline, ProductVariantInline]
    ordering = ('-created_at',)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = (
        'sku',
        'product',
        'clothing_type',
        'color',
        'size',
        'stock',
        'reserved_stock',
        'available_stock',
        'final_price',
    )
    list_filter = ('clothing_type', 'product__category', 'color', 'size')
    search_fields = ('sku', 'product__title')
    ordering = ('product', 'clothing_type', 'size__order')
