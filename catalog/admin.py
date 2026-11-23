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
    HeroSlide,
    ProductReview,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_per_page = 25
    list_display = (
        'name',
        'slug',
        'image_preview',
        'item_count_label',
        'display_order',
        'is_active',
        'created_at',
    )
    list_editable = ('display_order', 'is_active')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('image_preview',)
    ordering = ('display_order', 'name')

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 44px; height: 44px; object-fit: cover; border-radius: 50%; border: 1px solid #ddd;" />',
                obj.image.url,
            )
        return "—"
    image_preview.short_description = "Preview"


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
    fields = ('clothing_type', 'image', 'image_preview', 'color', 'order')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />',
                obj.image.url,
            )
        return "—"
    image_preview.short_description = "Preview"


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = (
        'clothing_type',
        'color',
        'size',
        'stock',
        'price_override',
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_per_page = 25
    list_display = (
        'title',
        'sku_prefix',
        'category',
        'feeding_config',
        'price',
        'mrp',
        'is_feeding_collection',
        'is_handstock',
        'is_sarees_collection',
        'is_kidswear_collection',
        'is_new_arrival',
        'is_best_seller',
        'is_active',
    )
    list_editable = (
        'is_feeding_collection',
        'is_handstock',
        'is_sarees_collection',
        'is_kidswear_collection',
        'is_new_arrival',
        'is_best_seller',
        'is_active',
    )
    list_filter = (
        'category',
        'feeding_config',
        'is_feeding_collection',
        'is_handstock',
        'is_sarees_collection',
        'is_kidswear_collection',
        'is_new_arrival',
        'is_best_seller',
        'is_active',
    )
    search_fields = ('title', 'sku_prefix', 'description', 'fabric')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ProductImageInline, ProductVariantInline]
    ordering = ('-created_at',)

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'title',
                'slug',
                'sku_prefix',
                'category',
                'price',
                'mrp',
                'is_active',
            ),
        }),
        ('Feeding Configuration', {
            'fields': ('feeding_config',),
            'description': (
                "Choose 'Both Feeding & Non-Feeding', 'Feeding Only', or 'Standard / None'. "
                "The product variants below adapt based on this configuration."
            ),
        }),
        ('Homepage Sections (Checklist)', {
            'fields': (
                'is_feeding_collection',
                'is_handstock',
                'is_sarees_collection',
                'is_kidswear_collection',
                'is_new_arrival',
                'is_best_seller',
            ),
            'description': 'Check the homepage carousels in which this product should appear.',
        }),
        ('Product Details & Styling', {
            'fields': (
                'fabric',
                'description',
                'care_instructions',
                'rating',
                'review_count',
            ),
            'classes': ('collapse',),
        }),
    )

    class Media:
        js = ('catalog/js/product_admin.js',)


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_per_page = 25
    list_display = ('title', 'cta_link', 'display_order', 'is_active', 'preview')
    list_editable = ('display_order', 'is_active')
    search_fields = ('title', 'cta_link')
    ordering = ('display_order', 'id')

    def preview(self, obj):
        if obj.desktop_image:
            return format_html('<img src="{}" style="height:36px; border-radius:4px; max-width:120px; object-fit:cover;" />', obj.desktop_image.url)
        return "-"
    preview.short_description = "Banner Preview"


class HomepageSectionItemInline(admin.TabularInline):
    model = HomepageSectionItem
    extra = 1
    fields = ('product', 'order')
    autocomplete_fields = ['product']


@admin.register(HomepageSection)
class HomepageSectionAdmin(admin.ModelAdmin):
    list_per_page = 25
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


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_per_page = 25
    list_display = (
        'product',
        'user_name',
        'star_rating_display',
        'image_preview',
        'headline',
        'verified_purchase_badge',
        'is_approved',
        'created_at',
    )
    list_editable = ('is_approved',)
    list_filter = ('rating', 'verified_purchase', 'is_approved', 'created_at')
    search_fields = ('product__title', 'user_name', 'user__email', 'headline', 'comment')
    readonly_fields = ('image_preview',)
    actions = ['approve_reviews', 'reject_reviews']

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="width: 44px; height: 44px; object-fit: cover; border-radius: 4px; border: 1px solid #ddd;" /></a>',
                obj.image.url,
                obj.image.url,
            )
        return "—"
    image_preview.short_description = 'Photo'

    def star_rating_display(self, obj):
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html('<span style="color: #F59E0B; font-weight: bold; font-size: 13px;">{}</span> ({})', stars, obj.rating)
    star_rating_display.short_description = 'Rating'

    def verified_purchase_badge(self, obj):
        if obj.verified_purchase:
            return format_html('<span style="background-color: #10B981; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold;">✓ Verified</span>')
        return format_html('<span style="color: #9CA3AF; font-size: 11px;">Standard</span>')
    verified_purchase_badge.short_description = 'Buyer Type'

    @admin.action(description="Approve selected customer reviews")
    def approve_reviews(self, request, queryset):
        count = queryset.update(is_approved=True)
        for obj in queryset:
            obj.recalculate_product_metrics()
        self.message_user(request, f"{count} review(s) approved and product ratings updated.")

    @admin.action(description="Reject selected customer reviews")
    def reject_reviews(self, request, queryset):
        count = queryset.update(is_approved=False)
        for obj in queryset:
            obj.recalculate_product_metrics()
        self.message_user(request, f"{count} review(s) rejected and product ratings updated.")




