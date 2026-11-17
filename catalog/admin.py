from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Category,
    Color,
    Size,
    Product,
    ProductImage,
    ProductVariant,
    HomepageSection,
    HomepageSectionItem,
    SiteConfig,
)


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


class HomepageSectionItemInline(admin.TabularInline):
    model = HomepageSectionItem
    extra = 1
    fields = ('product', 'order')
    autocomplete_fields = ['product']


@admin.register(HomepageSection)
class HomepageSectionAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'slug',
        'badge_label',
        'direction',
        'display_order',
        'is_active',
    )
    list_editable = ('display_order', 'is_active', 'direction')
    search_fields = ('title', 'slug', 'subtitle', 'badge_label')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [HomepageSectionItemInline]
    ordering = ('display_order', 'title')


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'cod_enabled', 'return_window_days', 'exchange_window_days', 'updated_at')
    fieldsets = (
        ('Legal & Taxation (Pending Confirmation)', {
            'fields': ('gstin', 'registered_address', 'tax_percentage', 'is_tax_inclusive'),
            'description': 'Storewide tax configurations. Leave unset/null until officially confirmed.',
        }),
        ('Shipping & Delivery Policies', {
            'fields': ('shipping_fee', 'free_shipping_threshold', 'shipping_notice'),
        }),
        ('Cash on Delivery (COD)', {
            'fields': ('cod_enabled', 'cod_extra_charge'),
        }),
        ('Return & Exchange Policy Windows', {
            'fields': ('return_window_days', 'exchange_window_days'),
            'description': 'Maximum days after delivery customer may initiate return or exchange requests.',
        }),
        ('Customer Limits', {
            'fields': ('max_saved_addresses',),
        }),
    )

    def has_add_permission(self, request):
        return not SiteConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False



