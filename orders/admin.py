from django.contrib import admin
from django.utils.html import format_html

from .models import FeedingOrder, NonFeedingOrder, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = [
        'product_name',
        'product_sku',
        'clothing_type_badge',
        'color',
        'size',
        'unit_price_display',
        'quantity',
        'line_total_display',
    ]
    readonly_fields = [
        'product_name',
        'product_sku',
        'clothing_type_badge',
        'color',
        'size',
        'unit_price_display',
        'quantity',
        'line_total_display',
    ]

    def clothing_type_badge(self, obj):
        colors = {
            'Feeding': '#EC4899',       # Pink badge for nursing garments
            'Non-Feeding': '#3B82F6',   # Blue badge for non-nursing garments
            'Standard': '#6B7280',      # Slate gray badge for standard garments
        }
        bg = colors.get(obj.clothing_type, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: #FFFFFF; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; letter-spacing: 0.5px;">{}</span>',
            bg,
            obj.clothing_type,
        )
    clothing_type_badge.short_description = 'Garment Type'

    def unit_price_display(self, obj):
        return f"₹{obj.unit_price:.2f}"
    unit_price_display.short_description = 'Unit Price'

    def line_total_display(self, obj):
        return f"₹{obj.line_total:.2f}"
    line_total_display.short_description = 'Line Total'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number',
        'customer_info',
        'clothing_breakdown',
        'tracking_display',
        'total_amount_display',
        'payment_status_badge',
        'order_status_badge',
        'created_at',
    ]
    list_filter = ['order_status', 'payment_status', 'payment_method', 'created_at']
    search_fields = ['order_number', 'first_name', 'last_name', 'phone', 'email', 'tracking_number', 'carrier_name']
    inlines = [OrderItemInline]
    actions = [
        'mark_as_processing',
        'mark_as_shipped',
        'mark_as_delivered',
        'cancel_selected_orders',
    ]
    readonly_fields = [
        'order_number',
        'subtotal_display',
        'shipping_fee_display',
        'discount_display',
        'total_amount_display',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('Order Identification', {
            'fields': ('order_number', 'user', 'order_status', 'payment_status', 'payment_method')
        }),
        ('Customer & Delivery Coordinates', {
            'fields': (
                ('first_name', 'last_name'),
                ('email', 'phone'),
                'shipping_address',
                'apartment',
                'landmark',
                ('city', 'state', 'zip_code'),
            )
        }),
        ('Financial Snapshot', {
            'fields': (
                'subtotal_display',
                'shipping_fee_display',
                'discount_display',
                'total_amount_display',
            )
        }),
        ('Fulfilment & Tracking', {
            'fields': (
                ('carrier_name', 'tracking_number'),
                ('razorpay_order_id', 'razorpay_payment_id'),
                ('created_at', 'updated_at'),
            )
        }),
    )

    def customer_info(self, obj):
        return f"{obj.full_name} ({obj.phone})"
    customer_info.short_description = 'Customer'

    def clothing_breakdown(self, obj):
        badges = []
        if obj.has_feeding_items:
            badges.append('<span style="background-color: #EC4899; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; margin-right: 4px;">Feeding</span>')
        if obj.has_non_feeding_items:
            badges.append('<span style="background-color: #3B82F6; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">Regular</span>')
        return format_html("".join(badges)) if badges else format_html('<span style="color: #9CA3AF;">None</span>')
    clothing_breakdown.short_description = 'Garments'

    def total_amount_display(self, obj):
        return f"₹{obj.total_amount:.2f}"
    total_amount_display.short_description = 'Grand Total'

    def subtotal_display(self, obj):
        return f"₹{obj.subtotal:.2f}"
    subtotal_display.short_description = 'Subtotal'

    def shipping_fee_display(self, obj):
        return f"₹{obj.shipping_fee:.2f}"
    shipping_fee_display.short_description = 'Shipping Fee'

    def discount_display(self, obj):
        return f"₹{obj.discount:.2f}"
    discount_display.short_description = 'Discount'

    def payment_status_badge(self, obj):
        colors = {
            'Paid': '#10B981',      # Emerald green
            'Pending': '#F59E0B',   # Amber
            'Failed': '#EF4444',    # Red
            'Refunded': '#6B7280',  # Gray
        }
        bg = colors.get(obj.payment_status, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            bg,
            obj.payment_status,
        )
    payment_status_badge.short_description = 'Payment'

    def order_status_badge(self, obj):
        colors = {
            'Ordered': '#3B82F6',           # Blue
            'Processing': '#8B5CF6',        # Purple
            'Shipped': '#06B6D4',           # Cyan
            'Delivered': '#10B981',         # Green
            'Cancelled': '#EF4444',         # Red
            'Requires_Attention': '#DC2626', # Bold Dark Red
        }
        bg = colors.get(obj.order_status, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            bg,
            obj.order_status,
        )
    def tracking_display(self, obj):
        if obj.tracking_number:
            carrier = f" ({obj.carrier_name})" if obj.carrier_name else ""
            return f"{obj.tracking_number}{carrier}"
        return format_html('<span style="color: #9CA3AF;">Pending</span>')
    tracking_display.short_description = 'Tracking'

    @admin.action(description="Mark selected orders as Processing")
    def mark_as_processing(self, request, queryset):
        count = queryset.filter(order_status='Ordered').update(order_status='Processing')
        self.message_user(request, f"{count} order(s) updated to Processing.")

    @admin.action(description="Mark selected orders as Shipped")
    def mark_as_shipped(self, request, queryset):
        count = queryset.filter(order_status='Processing').update(order_status='Shipped')
        self.message_user(request, f"{count} order(s) updated to Shipped.")

    @admin.action(description="Mark selected orders as Delivered")
    def mark_as_delivered(self, request, queryset):
        count = queryset.filter(order_status='Shipped').update(order_status='Delivered')
        self.message_user(request, f"{count} order(s) updated to Delivered.")

    @admin.action(description="Cancel selected orders (restores stock & triggers refund if paid)")
    def cancel_selected_orders(self, request, queryset):
        from django.db import transaction
        from django.db.models import F
        from catalog.models import ProductVariant
        from cart.models import StockReservation
        from payments.models import RefundRecord
        from payments.razorpay_client import dispatch_razorpay_refund

        cancelled_count = 0
        for order in queryset:
            if not order.is_cancellable:
                continue

            with transaction.atomic():
                if order.payment_status == 'Paid':
                    for item in order.items.all():
                        if item.variant_id:
                            ProductVariant.objects.filter(id=item.variant_id).update(
                                stock=F('stock') + item.quantity
                            )
                    if order.razorpay_payment_id:
                        idempotency_key = f"refund-cancel-admin-{order.order_number}"
                        try:
                            res = dispatch_razorpay_refund(
                                payment_id=order.razorpay_payment_id,
                                amount_paise=int(order.total_amount * 100),
                                idempotency_key=idempotency_key,
                                reason="Admin cancelled prior to shipment",
                            )
                            RefundRecord.objects.create(
                                order=order,
                                idempotency_key=idempotency_key,
                                amount=order.total_amount,
                                razorpay_refund_id=res.get('id'),
                                reason="Admin cancelled prior to shipment",
                                status=RefundRecord.STATUS_PROCESSED,
                            )
                            order.payment_status = 'Refunded'
                        except Exception:
                            pass
                else:
                    for res in StockReservation.objects.filter(order_number=order.order_number, status=StockReservation.STATUS_ACTIVE):
                        res.release()

                order.order_status = 'Cancelled'
                order.save(update_fields=['order_status', 'payment_status', 'updated_at'])
                cancelled_count += 1

        self.message_user(request, f"{cancelled_count} order(s) cancelled and inventory restored.")


@admin.register(FeedingOrder)
class FeedingOrderAdmin(OrderAdmin):
    """
    Dedicated admin view for warehouse staff fulfilling Feeding garment orders.
    Retains COMPLETE item visibility in the change form so mixed orders are packed accurately.
    """

    def get_queryset(self, request):
        return super().get_queryset(request).filter(items__clothing_type='Feeding').distinct()


@admin.register(NonFeedingOrder)
class NonFeedingOrderAdmin(OrderAdmin):
    """
    Dedicated admin view for warehouse staff fulfilling Non-Feeding / Standard garment orders.
    Retains COMPLETE item visibility in the change form so mixed orders are packed accurately.
    """

    def get_queryset(self, request):
        return super().get_queryset(request).filter(items__clothing_type__in=['Non-Feeding', 'Standard']).distinct()

