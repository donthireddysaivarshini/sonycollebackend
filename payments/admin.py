from django.contrib import admin
from django.utils.html import format_html

from .models import PaymentTransaction, RefundRecord
from .tasks import process_pending_refund_records


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'order_link',
        'gateway',
        'gateway_order_id',
        'gateway_payment_id',
        'amount_display',
        'status_badge',
        'created_at',
    ]
    list_filter = ['status', 'gateway', 'created_at']
    search_fields = ['order__order_number', 'gateway_order_id', 'gateway_payment_id']
    readonly_fields = [
        'order',
        'gateway',
        'gateway_order_id',
        'gateway_payment_id',
        'gateway_signature',
        'amount_display',
        'status',
        'raw_response',
        'created_at',
    ]

    def order_link(self, obj):
        return obj.order.order_number
    order_link.short_description = 'Order'

    def amount_display(self, obj):
        return f"₹{obj.amount:.2f}"
    amount_display.short_description = 'Amount'

    def status_badge(self, obj):
        colors = {
            'captured': '#10B981',  # Emerald green
            'initiated': '#3B82F6', # Blue
            'failed': '#EF4444',    # Red
            'refunded': '#6B7280',  # Slate gray
        }
        bg = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            bg,
            obj.status.capitalize(),
        )
    status_badge.short_description = 'Status'


# RefundRecord is intentionally omitted from admin registration because store policy is strictly
# NO RETURNS, NO COD, NO REFUNDS (damaged item exchanges only).
# class RefundRecordAdmin is retained without @admin.register for testing and integrity.
class RefundRecordAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'order_link',
        'amount_display',
        'status_badge',
        'razorpay_refund_id',
        'retry_count',
        'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['order__order_number', 'idempotency_key', 'razorpay_refund_id']
    readonly_fields = [
        'order',
        'payment',
        'idempotency_key',
        'amount_display',
        'razorpay_refund_id',
        'reason',
        'status',
        'error_message',
        'retry_count',
        'created_at',
        'updated_at',
    ]
    actions = ['retry_failed_refunds']

    def order_link(self, obj):
        return obj.order.order_number
    order_link.short_description = 'Order'

    def amount_display(self, obj):
        return f"₹{obj.amount:.2f}"
    amount_display.short_description = 'Amount'

    def status_badge(self, obj):
        colors = {
            'PROCESSED': '#10B981',        # Green
            'PENDING': '#F59E0B',          # Amber
            'FAILED_RETRYABLE': '#EF4444', # Red
            'FAILED_PERMANENT': '#991B1B', # Dark Red
        }
        bg = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            bg,
            obj.status,
        )
    status_badge.short_description = 'Refund State'

    @admin.action(description="Retry pending or failed recoverable refunds")
    def retry_failed_refunds(self, request, queryset):
        count = process_pending_refund_records()
        self.message_user(request, f"Processed {count} refund record(s).")

