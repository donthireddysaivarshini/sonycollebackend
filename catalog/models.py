from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal


class Category(models.Model):
    """
    Store product category (8 primary categories).
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    image = models.CharField(max_length=500, blank=True)
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
    is_new_arrival = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    is_handstock = models.BooleanField(default=False)
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
    Product gallery image ordered sequentially.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
    )
    image = models.CharField(max_length=500)
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
    sku = models.CharField(max_length=100, unique=True)
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


