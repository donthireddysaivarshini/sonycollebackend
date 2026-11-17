from decimal import Decimal

from django.db import models


class PaymentTransaction(models.Model):
    """
    Immutable ledger of all payment gateway transactions and callback attempts.
    """

    STATUS_INITIATED = 'initiated'
    STATUS_CAPTURED = 'captured'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'

    STATUS_CHOICES = (
        (STATUS_INITIATED, 'Initiated'),
        (STATUS_CAPTURED, 'Captured'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REFUNDED, 'Refunded'),
    )

    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    gateway = models.CharField(max_length=30, default='razorpay')
    gateway_order_id = models.CharField(max_length=100, db_index=True)
    gateway_payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    gateway_signature = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_INITIATED,
        db_index=True,
    )
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.gateway.upper()}] Order {self.order.order_number}: ₹{self.amount} ({self.status})"


class RefundRecord(models.Model):
    """
    Audit ledger of customer refunds with strict idempotency and recoverable retry tracking.
    Guarantees no duplicate refund requests are sent to the payment gateway.
    """

    STATUS_PENDING = 'PENDING'
    STATUS_PROCESSED = 'PROCESSED'
    STATUS_FAILED_RETRYABLE = 'FAILED_RETRYABLE'
    STATUS_FAILED_PERMANENT = 'FAILED_PERMANENT'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSED, 'Processed'),
        (STATUS_FAILED_RETRYABLE, 'Failed - Retryable'),
        (STATUS_FAILED_PERMANENT, 'Failed - Permanent'),
    )

    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='refunds',
    )
    payment = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds',
    )
    idempotency_key = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        help_text="Unique key preventing duplicate refund requests across retries.",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    razorpay_refund_id = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
    )
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Refund Record'
        verbose_name_plural = 'Refund Records'
        ordering = ['-created_at']

    def __str__(self):
        return f"Refund #{self.id} for {self.order.order_number}: ₹{self.amount} [{self.status}]"

