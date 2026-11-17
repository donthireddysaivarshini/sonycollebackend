import random
import string
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_order_number() -> str:
    """
    Generates a unique, non-sequential order code matching SFK-YYMM-XXXX.
    Example: SFK-2611-KJ7M
    """
    prefix = "SFK"
    yymm = timezone.now().strftime("%y%m")
    # Character set excluding easily confused characters (O, 0, I, 1)
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    while True:
        random_suffix = "".join(random.choices(chars, k=4))
        candidate = f"{prefix}-{yymm}-{random_suffix}"
        if not Order.objects.filter(order_number=candidate).exists():
            return candidate


class Order(models.Model):
    """
    Primary customer order model.
    Captures complete financial snapshot, delivery coordinates,
    and fulfillment status transitions.
    """

    PAYMENT_METHOD_CHOICES = (
        ('razorpay', 'Razorpay'),
        ('cod', 'Cash on Delivery'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Failed', 'Failed'),
        ('Refunded', 'Refunded'),
    )

    ORDER_STATUS_CHOICES = (
        ('Ordered', 'Ordered'),
        ('Processing', 'Processing'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
        ('Requires_Attention', 'Requires Attention'),
    )

    order_number = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(max_length=255, db_index=True)

    # Delivery Coordinates
    shipping_address = models.CharField(max_length=255)  # House / Flat / Building
    apartment = models.CharField(max_length=255, blank=True, default='')  # Street / Colony / Area
    landmark = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=10)

    # Authoritative Financial Snapshot
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Payment & Fulfilment State
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='razorpay',
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='Pending',
        db_index=True,
    )
    order_status = models.CharField(
        max_length=30,
        choices=ORDER_STATUS_CHOICES,
        default='Ordered',
        db_index=True,
    )

    # Shipping Logistics
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    carrier_name = models.CharField(max_length=100, blank=True, null=True)

    # Gateway References
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'All Orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_number} - {self.full_name} (₹{self.total_amount})"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = generate_order_number()
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_cancellable(self) -> bool:
        """Customers may cancel an order only prior to warehouse dispatch."""
        return self.order_status in ('Ordered', 'Processing')

    @property
    def items_count(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def has_feeding_items(self) -> bool:
        return self.items.filter(clothing_type='Feeding').exists()

    @property
    def has_non_feeding_items(self) -> bool:
        return self.items.filter(clothing_type__in=['Non-Feeding', 'Standard']).exists()


class OrderItem(models.Model):
    """
    Immutable line-item snapshot preserving historical order state.
    Protects order records from retroactive catalog price, name, or SKU modifications.
    """

    CLOTHING_TYPE_CHOICES = (
        ('Feeding', 'Feeding'),
        ('Non-Feeding', 'Non-Feeding'),
        ('Standard', 'Standard'),
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historical_order_items',
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historical_order_items',
    )

    # Immutable Snapshot Fields
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=100)
    product_image = models.CharField(max_length=500, blank=True, default='')
    clothing_type = models.CharField(
        max_length=20,
        choices=CLOTHING_TYPE_CHOICES,
        default='Standard',
        db_index=True,
    )
    color = models.CharField(max_length=100)
    size = models.CharField(max_length=50)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Order Line Item'
        verbose_name_plural = 'Order Line Items'
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}x {self.product_name} ({self.clothing_type} - {self.size}) in {self.order.order_number}"

    def save(self, *args, **kwargs):
        if self.unit_price is not None and self.quantity is not None:
            self.line_total = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class FeedingOrderManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(items__clothing_type='Feeding').distinct()


class NonFeedingOrderManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(items__clothing_type__in=['Non-Feeding', 'Standard']).distinct()


class FeedingOrder(Order):
    """
    Proxy model for warehouse fulfilment staff specializing in nursing garments.
    Queryset filters orders containing at least one Feeding garment.
    """

    objects = FeedingOrderManager()

    class Meta:
        proxy = True
        verbose_name = 'Feeding Order'
        verbose_name_plural = 'Feeding Orders'


class NonFeedingOrder(Order):
    """
    Proxy model for warehouse staff managing standard apparel and non-nursing garments.
    Queryset filters orders containing at least one Non-Feeding or Standard garment.
    """

    objects = NonFeedingOrderManager()

    class Meta:
        proxy = True
        verbose_name = 'Non-Feeding Order'
        verbose_name_plural = 'Non-Feeding Orders'

