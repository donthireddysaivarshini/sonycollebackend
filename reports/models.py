from decimal import Decimal

from django.db import models
from django.utils import timezone


def generate_invoice_number(order_number: str) -> str:
    """
    Generates deterministic legal invoice number from order number.
    Example: SFK-2611-KJ7M -> INV-SFK-2611-KJ7M
    """
    return f"INV-{order_number}"


class Invoice(models.Model):
    """
    Legal tax invoice snapshot generated upon order payment.
    Captures applicable GST details and links generated PDF document.
    """

    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
    )
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='invoice',
    )
    pdf_file = models.FileField(
        upload_to='invoices/',
        blank=True,
        null=True,
    )
    gst_number = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=10, decimal_places=2)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tax Invoice'
        verbose_name_plural = 'Tax Invoices'
        ordering = ['-issued_at']

    def __str__(self):
        return f"{self.invoice_number} for Order {self.order.order_number} (₹{self.grand_total})"
