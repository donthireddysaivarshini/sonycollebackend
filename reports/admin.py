from django.contrib import admin
from django.utils.html import format_html
from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'invoice_number',
        'order_link',
        'customer_name',
        'subtotal_display',
        'tax_display',
        'grand_total_display',
        'download_pdf_link',
        'issued_at',
    ]
    list_filter = ['issued_at']
    search_fields = [
        'invoice_number',
        'order__order_number',
        'order__first_name',
        'order__last_name',
        'order__email',
        'gst_number',
    ]
    readonly_fields = [
        'invoice_number',
        'order',
        'pdf_file',
        'gst_number',
        'subtotal',
        'tax_amount',
        'grand_total',
        'issued_at',
    ]

    def order_link(self, obj):
        return obj.order.order_number
    order_link.short_description = 'Order Number'

    def customer_name(self, obj):
        return obj.order.full_name
    customer_name.short_description = 'Customer'

    def subtotal_display(self, obj):
        return f"₹{obj.subtotal:.2f}"
    subtotal_display.short_description = 'Subtotal'

    def tax_display(self, obj):
        return f"₹{obj.tax_amount:.2f}"
    tax_display.short_description = 'Tax'

    def grand_total_display(self, obj):
        return f"₹{obj.grand_total:.2f}"
    grand_total_display.short_description = 'Grand Total'

    def download_pdf_link(self, obj):
        if obj.pdf_file:
            return format_html(
                '<a href="{}" target="_blank" style="color: #BE185D; font-weight: 600;">Download PDF</a>',
                obj.pdf_file.url,
            )
        return "No PDF"
    download_pdf_link.short_description = 'PDF File'

    def has_add_permission(self, request):
        return False
