from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Case, F, Value, When
from django.utils import timezone


class Cart(models.Model):
    """
    Shopping cart supporting both guest visitors (session_key)
    and authenticated customers (user).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='carts',
    )
    session_key = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Shopping Cart'
        verbose_name_plural = 'Shopping Carts'
        ordering = ['-updated_at']

    def __str__(self):
        owner = self.user.email if self.user else f"Guest ({self.session_key})"
        return f"Cart #{self.id} for {owner} ({self.items_count} items)"

    @property
    def items_count(self) -> int:
        """Total unit count of all items in cart."""
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self) -> Decimal:
        """Authoritative subtotal calculated from DB variant prices."""
        return sum(
            (item.line_total for item in self.items.select_related('variant', 'variant__product')),
            Decimal('0.00'),
        )

    @property
    def shipping_fee(self) -> Decimal:
        """Standard shipping fee (default 0.00 pending client policy confirmation)."""
        return Decimal('0.00')

    @property
    def tax_amount(self) -> Decimal:
        """Applicable tax (default 0.00 pending client policy confirmation)."""
        return Decimal('0.00')

    @property
    def grand_total(self) -> Decimal:
        """Authoritative grand total."""
        return self.subtotal + self.shipping_fee + self.tax_amount

    def clear(self):
        """Remove all items from this cart."""
        self.items.all().delete()


class CartItem(models.Model):
    """
    Individual line item in a customer's shopping cart.
    Binds directly to a specific catalog.ProductVariant (color + size + clothing_type).
    """

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        related_name='cart_items',
    )
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['cart', 'variant'],
                name='unique_cart_variant',
            )
        ]

    def __str__(self):
        return f"{self.quantity}x {self.variant.product.title} ({self.variant.sku}) in Cart #{self.cart_id}"

    @property
    def unit_price(self) -> Decimal:
        """Authoritative unit price from variant final_price."""
        return self.variant.final_price

    @property
    def line_total(self) -> Decimal:
        """Authoritative line total = unit_price * quantity."""
        return self.unit_price * self.quantity

    @property
    def available_stock(self) -> int:
        """Live available stock from catalog variant."""
        return self.variant.available_stock

    @property
    def is_available(self) -> bool:
        """True if variant is available and product is active."""
        return (
            self.variant.product.is_active
            and self.variant.available_stock >= self.quantity
        )


class StockReservation(models.Model):
    """
    Transient 15-minute stock hold during checkout to protect against overselling.
    Coordinates between cart checkout initiation and Razorpay payment capture.
    """

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_RELEASED = 'RELEASED'
    STATUS_CONVERTED = 'CONVERTED_TO_SALE'
    STATUS_EXPIRED = 'EXPIRED'

    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Active'),
        (STATUS_RELEASED, 'Released'),
        (STATUS_CONVERTED, 'Converted to Sale'),
        (STATUS_EXPIRED, 'Expired'),
    )

    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        related_name='reservations',
    )
    quantity = models.PositiveIntegerField(default=1)
    session_key = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_reservations',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='stock_reservations',
    )
    order_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
    )
    expires_at = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Stock Reservation'
        verbose_name_plural = 'Stock Reservations'
        ordering = ['-created_at']

    def __str__(self):
        return f"Hold #{self.id}: {self.quantity}x {self.variant.sku} [{self.status}] (expires {self.expires_at})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def release(self):
        """Release reservation hold back to available stock."""
        from catalog.models import ProductVariant

        with transaction.atomic():
            locked = StockReservation.objects.select_for_update().get(id=self.id)
            if locked.status == self.STATUS_ACTIVE:
                ProductVariant.objects.filter(id=locked.variant_id).update(
                    reserved_stock=Case(
                        When(reserved_stock__gte=locked.quantity, then=F('reserved_stock') - locked.quantity),
                        default=Value(0),
                    )
                )
                locked.status = self.STATUS_RELEASED
                locked.save(update_fields=['status'])
                self.status = self.STATUS_RELEASED

    def expire(self):
        """Mark reservation expired and restore reserved stock."""
        from catalog.models import ProductVariant

        with transaction.atomic():
            locked = StockReservation.objects.select_for_update().get(id=self.id)
            if locked.status == self.STATUS_ACTIVE:
                ProductVariant.objects.filter(id=locked.variant_id).update(
                    reserved_stock=Case(
                        When(reserved_stock__gte=locked.quantity, then=F('reserved_stock') - locked.quantity),
                        default=Value(0),
                    )
                )
                locked.status = self.STATUS_EXPIRED
                locked.save(update_fields=['status'])
                self.status = self.STATUS_EXPIRED

    def convert_to_sale(self):
        """Convert hold to permanent sale: decrement both reserved_stock and physical stock."""
        from catalog.models import ProductVariant

        with transaction.atomic():
            locked = StockReservation.objects.select_for_update().get(id=self.id)
            if locked.status == self.STATUS_ACTIVE:
                ProductVariant.objects.filter(id=locked.variant_id).update(
                    reserved_stock=Case(
                        When(reserved_stock__gte=locked.quantity, then=F('reserved_stock') - locked.quantity),
                        default=Value(0),
                    ),
                    stock=Case(
                        When(stock__gte=locked.quantity, then=F('stock') - locked.quantity),
                        default=Value(0),
                    ),
                )
                locked.status = self.STATUS_CONVERTED
                locked.save(update_fields=['status'])
                self.status = self.STATUS_CONVERTED

    @classmethod
    def create_reservation(cls, variant, quantity: int, user=None, session_key=None, order_number=None, ttl_minutes: int = 15):
        """
        Atomically reserve units under select_for_update() row lock.
        Validates available_stock and increments variant.reserved_stock.
        """
        from catalog.models import ProductVariant

        with transaction.atomic():
            # First lazily expire any stale reservations for this variant
            cls.expire_stale_reservations(variant_id=variant.id)

            locked_variant = ProductVariant.objects.select_for_update().get(id=variant.id)
            if locked_variant.available_stock < quantity:
                raise ValidationError(
                    f"Only {locked_variant.available_stock} unit(s) available for selected variant."
                )

            # Atomically increment reserved_stock
            ProductVariant.objects.filter(id=locked_variant.id).update(
                reserved_stock=F('reserved_stock') + quantity
            )

            expires_at = timezone.now() + timedelta(minutes=ttl_minutes)
            reservation = cls.objects.create(
                variant=locked_variant,
                quantity=quantity,
                user=user,
                session_key=session_key,
                order_number=order_number,
                expires_at=expires_at,
                status=cls.STATUS_ACTIVE,
            )
            return reservation

    @classmethod
    def expire_stale_reservations(cls, variant_id: int = None) -> int:
        """
        Lazy and periodic expiration of past-TTL active reservations.
        Restores reserved_stock to available pool atomically.
        """
        now = timezone.now()
        qs = cls.objects.filter(status=cls.STATUS_ACTIVE, expires_at__lte=now)
        if variant_id:
            qs = qs.filter(variant_id=variant_id)

        stale_ids = list(qs.values_list('id', flat=True))
        expired_count = 0
        for reservation_id in stale_ids:
            try:
                res = cls.objects.get(id=reservation_id)
                res.expire()
                expired_count += 1
            except Exception:
                pass
        return expired_count

