from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Category(models.Model):
    """
    Store product category (8 primary categories).
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    description = models.TextField(blank=True)
    tagline = models.CharField(max_length=200, blank=True)
    item_count_label = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class Color(models.Model):
    """
    Garment color attribute with display name and HEX swatch code.
    """

    name = models.CharField(max_length=50, unique=True)
    hex_code = models.CharField(max_length=10, default='#7c3aed')

    class Meta:
        verbose_name = 'Color'
        verbose_name_plural = 'Colors'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.hex_code})"


class Size(models.Model):
    """
    Garment size attribute with standardized ordering.
    """

    name = models.CharField(max_length=20, unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Size'
        verbose_name_plural = 'Sizes'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Master Product entity.
    Maintains a 3-way feeding configuration ('both', 'feeding-only', 'none').
    Never duplicated just to represent feeding options.
    """

    FEEDING_CONFIG_CHOICES = (
        ('both', 'Both Feeding & Non-Feeding'),
        ('feeding-only', 'Feeding Only'),
        ('none', 'Standard / None'),
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    sku_prefix = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products',
    )
    feeding_config = models.CharField(
        max_length=20,
        choices=FEEDING_CONFIG_CHOICES,
        default='both',
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Selling Price
    mrp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True)
    fabric = models.CharField(max_length=150, blank=True)
    care_instructions = models.TextField(blank=True)

    # Homepage Sections Checklist
    is_feeding_collection = models.BooleanField(
        default=False,
        verbose_name="Feeding & Non-Feeding Section",
        help_text="Check to display in 'Feeding & Non-Feeding' carousel on homepage",
    )
    is_handstock = models.BooleanField(
        default=False,
        verbose_name="Handstock Section",
        help_text="Check to display in 'Handstock (Ready to Ship)' carousel on homepage",
    )
    is_sarees_collection = models.BooleanField(
        default=False,
        verbose_name="Sarees Section",
        help_text="Check to display in 'Sarees' carousel on homepage",
    )
    is_kidswear_collection = models.BooleanField(
        default=False,
        verbose_name="Kids Wear Section",
        help_text="Check to display in 'Kids Wear' carousel on homepage",
    )
    is_new_arrival = models.BooleanField(
        default=False,
        verbose_name="New Arrivals Section",
        help_text="Check to display in 'New Arrivals' carousel on homepage",
    )
    is_best_seller = models.BooleanField(
        default=False,
        verbose_name="Best Sellers Section",
        help_text="Check to display in 'Best Sellers' carousel on homepage",
    )

    is_active = models.BooleanField(default=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('4.80'))
    review_count = models.PositiveIntegerField(default=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.sku_prefix})"

    @property
    def discount_percentage(self):
        if self.mrp and self.mrp > self.price:
            return round(((self.mrp - self.price) / self.mrp) * 100)
        return 0


class ProductImage(models.Model):
    """
    Product gallery image mapped to clothing type, color, and display order.
    """

    IMAGE_CLOTHING_TYPE_CHOICES = (
        ('Feeding', 'Feeding'),
        ('Non-Feeding', 'Non-Feeding'),
        ('Standard', 'Standard'),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
    )
    clothing_type = models.CharField(
        max_length=20,
        choices=IMAGE_CLOTHING_TYPE_CHOICES,
        default='Feeding',
        blank=True,
        null=True,
        help_text="Clothing type (Feeding, Non-Feeding, or Standard)",
    )
    image = models.ImageField(upload_to='products/')
    color = models.ForeignKey(
        Color,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_images',
        help_text="Optional color match for this image",
    )
    order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'
        ordering = ['order', 'id']

    def __str__(self):
        return f"Image {self.order} for {self.product.title}"


class ProductVariant(models.Model):
    """
    SKU-level product variant combination.
    Enforces non-null clothing_type ('Feeding', 'Non-Feeding', 'Standard')
    to prevent duplicate variant combinations in PostgreSQL/SQLite.
    """

    CLOTHING_TYPE_CHOICES = (
        ('Feeding', 'Feeding'),
        ('Non-Feeding', 'Non-Feeding'),
        ('Standard', 'Standard'),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
    )
    clothing_type = models.CharField(
        max_length=20,
        choices=CLOTHING_TYPE_CHOICES,
        default='Standard',
    )
    color = models.ForeignKey(
        Color,
        on_delete=models.PROTECT,
        related_name='variants',
    )
    size = models.ForeignKey(
        Size,
        on_delete=models.PROTECT,
        related_name='variants',
    )
    sku = models.CharField(max_length=100, unique=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    reserved_stock = models.PositiveIntegerField(default=0)
    price_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'clothing_type', 'color', 'size'],
                name='unique_product_variant_combination',
            )
        ]
        ordering = ['product', 'clothing_type', 'size__order']

    def __str__(self):
        return f"{self.product.title} - {self.clothing_type} - {self.color.name} - {self.size.name} ({self.sku})"

    def save(self, *args, **kwargs):
        if not self.sku:
            clothing_code = (self.clothing_type[:2] if self.clothing_type else 'ST').upper()
            color_code = (self.color.name[:3] if self.color else 'CLR').upper().replace(' ', '')
            size_code = self.size.name if self.size else 'STD'
            prefix = self.product.sku_prefix or 'SKU'
            base_sku = f"{prefix}-{clothing_code}-{color_code}-{size_code}".replace(' ', '')
            candidate = base_sku
            counter = 1
            while ProductVariant.objects.filter(sku=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_sku}-{counter}"
                counter += 1
            self.sku = candidate
        super().save(*args, **kwargs)

    @property
    def available_stock(self):
        """Authoritative available stock excluding active checkout holds."""
        return max(0, self.stock - self.reserved_stock)

    @property
    def final_price(self):
        """Effective selling price considering any variant-level override."""
        return self.price_override if self.price_override is not None else self.product.price

    def clean(self):
        """
        Cross-model business rule validation:
        Validates clothing_type against parent product.feeding_config.
        """
        super().clean()
        if not self.product_id:
            return

        config = self.product.feeding_config

        if config == 'both' and self.clothing_type not in ('Feeding', 'Non-Feeding'):
            raise ValidationError({
                'clothing_type': "For products with feeding_config='both', clothing_type must be 'Feeding' or 'Non-Feeding'."
            })
        elif config == 'feeding-only' and self.clothing_type != 'Feeding':
            raise ValidationError({
                'clothing_type': "For products with feeding_config='feeding-only', clothing_type must be 'Feeding'."
            })
        elif config == 'none' and self.clothing_type != 'Standard':
            raise ValidationError({
                'clothing_type': "For standard products with feeding_config='none', clothing_type must be 'Standard'."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class HomepageSection(models.Model):
    """
    Predefined merchandising sections for the storefront homepage.
    Distinct from categories: products can belong to multiple sections.
    """

    DIRECTION_CHOICES = (
        ('left', 'Left'),
        ('right', 'Right'),
    )

    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    subtitle = models.CharField(max_length=255, blank=True)
    badge_label = models.CharField(max_length=50, blank=True)
    view_all_link = models.CharField(max_length=255, blank=True)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='left')
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Homepage Section'
        verbose_name_plural = 'Homepage Sections'
        ordering = ['display_order', 'title']

    def __str__(self):
        return f"{self.title} (Order: {self.display_order})"


class HomepageSectionItem(models.Model):
    """
    Through model maintaining explicit ordering of products within a homepage section.
    """

    section = models.ForeignKey(
        HomepageSection,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='section_items',
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Homepage Section Item'
        verbose_name_plural = 'Homepage Section Items'
        ordering = ['order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['section', 'product'],
                name='unique_section_product',
            )
        ]

    def __str__(self):
        return f"{self.product.title} in {self.section.title} (Pos: {self.order})"


class SiteConfig(models.Model):
    """
    Singleton configuration model centralizing all store-wide business policies.
    """

    gstin = models.CharField(max_length=30, blank=True, null=True, default=None)
    registered_address = models.TextField(blank=True, null=True, default=None)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    is_tax_inclusive = models.BooleanField(default=True)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('99.00'))
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1499.00'))
    cod_enabled = models.BooleanField(default=False)
    cod_extra_charge = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, default=None)
    return_window_days = models.PositiveIntegerField(blank=True, null=True, default=None)
    exchange_window_days = models.PositiveIntegerField(default=7)
    max_saved_addresses = models.PositiveIntegerField(default=3)
    shipping_notice = models.CharField(max_length=255, default='Free shipping across India on orders above ₹1499')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Configuration'
        verbose_name_plural = 'Site Configuration'

    def __str__(self):
        return "Store Configuration (Singleton)"

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'shipping_fee': Decimal('99.00'),
                'free_shipping_threshold': Decimal('1499.00'),
                'shipping_notice': 'Free shipping across India on orders above ₹1499',
                'exchange_window_days': 7,
                'max_saved_addresses': 3,
                'tax_percentage': Decimal('5.00'),
                'is_tax_inclusive': True,
                'cod_enabled': False,
            }
        )
        # Populate defaults if existing singleton has nulls
        changed = False
        if obj.shipping_fee is None:
            obj.shipping_fee = Decimal('99.00')
            changed = True
        if obj.free_shipping_threshold is None:
            obj.free_shipping_threshold = Decimal('1499.00')
            changed = True
        if not obj.shipping_notice:
            obj.shipping_notice = 'Free shipping across India on orders above ₹1499'
            changed = True
        if obj.exchange_window_days is None:
            obj.exchange_window_days = 7
            changed = True
        if obj.max_saved_addresses is None:
            obj.max_saved_addresses = 3
            changed = True
        if changed:
            obj.save()
        return obj

    def save(self, *args, **kwargs):
        self.id = 1
        super().save(*args, **kwargs)


class HeroSlide(models.Model):
    """
    Hero promotion banner slide displayed at the top of the storefront homepage.
    Managed via Django Admin.
    """

    title = models.CharField(max_length=200, help_text="Slide heading or promotion title")
    desktop_image = models.ImageField(
        upload_to='hero/desktop/',
        blank=True,
        null=True,
        help_text="Desktop banner image",
    )
    mobile_image = models.ImageField(
        upload_to='hero/mobile/',
        blank=True,
        null=True,
        help_text="Mobile banner image (falls back to desktop image if blank)",
    )
    cta_link = models.CharField(
        max_length=255,
        default='/shop',
        help_text="Destination route when customer clicks banner (e.g. /shop, /shop?clothingType=Feeding)",
    )
    preserve_artwork = models.BooleanField(
        default=True,
        help_text="Preserve full graphic artwork aspect ratio without cropping",
    )
    display_order = models.PositiveIntegerField(default=0, help_text="Lower number shows first")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Hero Slide'
        verbose_name_plural = 'Hero Slides'
        ordering = ['display_order', 'id']

    def __str__(self):
        return f"{self.title} (Order: {self.display_order})"


class ProductReview(models.Model):
    """
    Amazon-style Customer Review & Rating entity.
    Only logged-in customers can submit reviews.
    Checks historical paid order items for Verified Buyer status.
    Automatically recalculates Product average rating and review_count.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='customer_reviews',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='product_reviews',
    )
    user_name = models.CharField(max_length=150, blank=True)
    rating = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1 to 5 star rating",
    )
    headline = models.CharField(max_length=255, blank=True)
    comment = models.TextField()
    image = models.ImageField(upload_to='reviews/', blank=True, null=True, help_text="Customer photo attachment")
    verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product Review'
        verbose_name_plural = 'Product Reviews'
        ordering = ['-created_at']
        unique_together = ('product', 'user')

    def __str__(self):
        return f"{self.rating}★ review by {self.user_name or self.user.email} on {self.product.title}"

    def save(self, *args, **kwargs):
        if not self.user_name:
            full = f"{getattr(self.user, 'first_name', '')} {getattr(self.user, 'last_name', '')}".strip()
            self.user_name = full or (self.user.email.split('@')[0] if self.user.email else 'Verified Customer')
        super().save(*args, **kwargs)
        self.recalculate_product_metrics()

    def delete(self, *args, **kwargs):
        product = self.product
        super().delete(*args, **kwargs)
        ProductReview.recalculate_metrics_for_product(product)

    def recalculate_product_metrics(self):
        ProductReview.recalculate_metrics_for_product(self.product)

    @classmethod
    def recalculate_metrics_for_product(cls, product):
        approved = cls.objects.filter(product=product, is_approved=True)
        count = approved.count()
        if count > 0:
            from django.db.models import Avg
            avg_val = approved.aggregate(Avg('rating'))['rating__avg'] or 5.0
            product.rating = Decimal(str(round(avg_val, 2)))
            product.review_count = count
        else:
            product.rating = Decimal('4.80')
            product.review_count = 0
        product.save(update_fields=['rating', 'review_count'])





