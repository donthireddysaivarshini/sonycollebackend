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
    coupon_code = models.CharField(max_length=50, blank=True, default='')
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


class ReturnRequest(models.Model):
    """
    Formal customer return request initiated after delivery.
    Subject to admin review, warehouse receipt inspection, and prorated refund.
    """

    STATUS_REQUESTED = 'Requested'
    STATUS_APPROVED = 'Approved'
    STATUS_REJECTED = 'Rejected'
    STATUS_ITEM_RECEIVED = 'Item Received'
    STATUS_REFUNDED = 'Refunded'

    STATUS_CHOICES = (
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_ITEM_RECEIVED, 'Item Received'),
        (STATUS_REFUNDED, 'Refunded'),
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='return_requests',
    )
    item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name='return_requests',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='return_requests',
    )
    reason = models.CharField(max_length=100)
    customer_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_REQUESTED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Return Request'
        verbose_name_plural = 'Return Requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"Return #{self.id} for {self.item.product_name} ({self.order.order_number}) - {self.status}"


class ExchangeRequest(models.Model):
    """
    Formal customer exchange request initiated after delivery for damaged goods.
    Specifies damage reason, proof photo/video upload, and generates single-use exchange coupon on approval.
    """

    STATUS_REQUESTED = 'Requested'
    STATUS_APPROVED = 'Approved'
    STATUS_REJECTED = 'Rejected'
    STATUS_DISPATCHED = 'Item Dispatched'

    STATUS_CHOICES = (
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_DISPATCHED, 'Item Dispatched'),
    )

    REASON_CHOICES = (
        ('damaged', 'Received damaged product'),
        ('other', 'Other'),
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='exchange_requests',
    )
    item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name='exchange_requests',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exchange_requests',
    )
    replacement_variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exchange_requests',
    )
    reason = models.CharField(
        max_length=50,
        choices=REASON_CHOICES,
        default='damaged',
    )
    other_reason = models.TextField(blank=True, default='')
    proof_file = models.FileField(
        upload_to='exchanges/',
        blank=True,
        null=True,
        help_text="Mandatory photo or unboxing video showing the damage",
    )
    exchange_code = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Single-use store credit code generated upon admin approval",
    )
    customer_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_REQUESTED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Exchange Request'
        verbose_name_plural = 'Exchange Requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"Exchange #{self.id} for {self.item.product_name} ({self.order.order_number}) - {self.status}"


class Coupon(models.Model):
    """
    Promotional discounts, boutique marketing coupons, and customer exchange credit codes.
    Aligns with Shruthis reference architecture and standard eCommerce practice.
    """

    DISCOUNT_TYPE_CHOICES = (
        ('percentage', 'Percentage (%)'),
        ('fixed', 'Fixed Amount (₹)'),
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Coupon or exchange code entered at checkout (e.g. WELCOME10, EXCHANGE500)",
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default='fixed',
    )
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Discount value: percentage number (e.g. 10 for 10%) or flat rupee amount (e.g. 150)",
    )
    min_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Minimum subtotal required to apply this coupon (₹)",
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum discount cap for percentage coupons (optional)",
    )
    valid_from = models.DateTimeField(
        help_text="Start date & time of validity",
    )
    valid_to = models.DateTimeField(
        help_text="Expiry date & time of validity",
    )
    active = models.BooleanField(
        default=True,
        help_text="Toggle to temporarily disable without deleting",
    )
    usage_limit = models.PositiveIntegerField(
        default=100,
        help_text="Maximum number of times this coupon can be redeemed across all customers",
    )
    uses_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this coupon has been applied in completed checkouts",
    )
    is_exchange_code = models.BooleanField(
        default=False,
        help_text="Designates this code as a customer exchange store credit voucher",
    )
    exchange_request = models.ForeignKey(
        'ExchangeRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_coupons',
        help_text="Optional link to customer exchange request if generated as store credit",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Internal notes or customer-facing promo description",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Coupon'
        verbose_name_plural = 'Coupons'
        ordering = ['-created_at']

    def __str__(self):
        type_str = f"{self.value}%" if self.discount_type == 'percentage' else f"₹{self.value}"
        exchange_str = " [Exchange Credit]" if self.is_exchange_code else ""
        return f"{self.code} ({type_str} off){exchange_str}"

    def calculate_discount(self, order_total: Decimal) -> Decimal:
        """
        Calculate applicable discount given a cart subtotal.
        """
        if self.discount_type == 'percentage':
            disc = (order_total * self.value) / Decimal('100.00')
            if self.max_discount_amount and disc > self.max_discount_amount:
                disc = self.max_discount_amount
        else:
            disc = self.value
        return min(disc, order_total)

    def is_valid_for(self, order_total: Decimal) -> tuple[bool, str]:
        now = timezone.now()
        if not self.active:
            return False, "This coupon is currently inactive."
        if now < self.valid_from:
            return False, "This coupon is not yet valid."
        if now > self.valid_to:
            return False, "This coupon has expired."
        if self.uses_count >= self.usage_limit:
            return False, "Coupon usage limit has been reached."
        if order_total < self.min_order_value:
            return False, f"Minimum order value of ₹{self.min_order_value:.0f} required to apply this coupon."
        return True, "Valid"



