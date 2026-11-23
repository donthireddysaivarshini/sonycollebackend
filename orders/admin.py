from django.contrib import admin
from django.utils.html import format_html

from .models import (
    FeedingOrder,
    NonFeedingOrder,
    Order,
    OrderItem,
    ReturnRequest,
    ExchangeRequest,
    Coupon,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    verbose_name = 'Order Line Item'
    verbose_name_plural = 'Order Line Items'
    extra = 0
    can_delete = False
    fields = [
        'product_image_preview',
        'product_name_display',
        'product_sku',
        'clothing_type_badge',
        'color',
        'size',
        'unit_price_display',
        'quantity',
        'line_total_display',
    ]
    readonly_fields = [
        'product_image_preview',
        'product_name_display',
        'product_sku',
        'clothing_type_badge',
        'color',
        'size',
        'unit_price_display',
        'quantity',
        'line_total_display',
    ]

    def product_image_preview(self, obj):
        if not obj or not getattr(obj, 'product_image', None):
            return format_html('<div style="width: 44px; height: 54px; background: #2D3748; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: #718096; font-size: 10px;">No img</div>')
        img_url = str(obj.product_image).strip()
        if not (img_url.startswith('http://') or img_url.startswith('https://')):
            clean_url = img_url.lstrip('/')
            img_url = f"/media/{clean_url}" if not img_url.startswith('/media/') else img_url
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer" title="Click to view full image in new tab">'
            '<img src="{}" alt="{}" style="width: 46px; height: 56px; object-fit: cover; border-radius: 6px; border: 1px solid rgba(255,255,255,0.25); box-shadow: 0 1px 3px rgba(0,0,0,0.3); cursor: pointer; transition: transform 0.15s ease;" onmouseover="this.style.transform=\'scale(1.08)\'" onmouseout="this.style.transform=\'scale(1)\'" />'
            '</a>',
            img_url,
            img_url,
            obj.product_name,
        )
    product_image_preview.short_description = 'Image'

    def product_name_display(self, obj):
        if not obj:
            return "-"
        if obj.product:
            admin_url = f"/admin/catalog/product/{obj.product.id}/change/"
            store_url = f"http://localhost:5173/product/{obj.product.slug}"
            return format_html(
                '<div style="font-weight: 600; color: #F3F4F6;">{}</div>'
                '<div style="margin-top: 4px; display: flex; gap: 8px; font-size: 11px;">'
                '<a href="{}" target="_blank" style="color: #EC4899; text-decoration: underline;" title="Edit product in admin">Admin Edit ↗</a>'
                '<a href="{}" target="_blank" style="color: #60A5FA; text-decoration: underline;" title="View product in storefront">Storefront ↗</a>'
                '</div>',
                obj.product_name,
                admin_url,
                store_url,
            )
        return obj.product_name
    product_name_display.short_description = 'Product Name'

    def clothing_type_badge(self, obj):
        if not obj or not getattr(obj, 'clothing_type', None):
            return format_html('<span style="color: #9CA3AF;">-</span>')
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
        if not obj or getattr(obj, 'unit_price', None) is None:
            return "₹0.00"
        return f"₹{float(obj.unit_price):.2f}"
    unit_price_display.short_description = 'Unit Price'

    def line_total_display(self, obj):
        if not obj or getattr(obj, 'line_total', None) is None:
            return "₹0.00"
        return f"₹{float(obj.line_total):.2f}"
    line_total_display.short_description = 'Line Total'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_per_page = 25
    jazzmin_section_order = (
        'Order Identification',
        'Customer & Delivery Coordinates',
        'Order Line Items',
        'Financial Snapshot',
        'Fulfilment & Tracking',
    )
    list_display = [
        'order_number',
        'customer_info',
        'clothing_breakdown',
        'tracking_display',
        'total_amount_display',
        'payment_status_badge',
        'order_status',
        'invoice_action',
        'created_at',
    ]
    list_editable = ['order_status']
    list_filter = ['order_status', 'payment_status', 'payment_method', 'created_at']
    search_fields = ['order_number', 'first_name', 'last_name', 'phone', 'email', 'tracking_number', 'carrier_name']
    inlines = [OrderItemInline]
    actions = [
        'mark_as_processing',
        'mark_as_shipped',
        'mark_as_delivered',
        'cancel_selected_orders',
        'export_orders_to_excel_action',
    ]
    readonly_fields = [
        'order_number',
        'invoice_link',
        'coupon_code',
        'subtotal_display',
        'shipping_fee_display',
        'discount_display',
        'total_amount_display',
        'formatted_address_with_copy',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('Order Identification', {
            'fields': (
                ('order_number', 'invoice_link'),
                'user',
                ('order_status', 'payment_status', 'payment_method'),
            )
        }),
        ('Customer & Delivery Coordinates', {
            'fields': (
                ('first_name', 'last_name'),
                ('email', 'phone'),
                'shipping_address',
                'apartment',
                'landmark',
                ('city', 'state', 'zip_code'),
                'formatted_address_with_copy',
            )
        }),
        ('Financial Snapshot', {
            'fields': (
                'subtotal_display',
                ('discount_display', 'coupon_code'),
                'shipping_fee_display',
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

    def formatted_address_with_copy(self, obj):
        if not obj:
            return "-"
        lines = [
            f"Name: {obj.full_name}",
            f"Phone: +91 {obj.phone}",
            f"Email: {obj.email}",
            f"Address: {obj.shipping_address}",
        ]
        if obj.apartment:
            lines.append(f"Street/Area: {obj.apartment}")
        if obj.landmark:
            lines.append(f"Landmark: {obj.landmark}")
        lines.append(f"City/State/PIN: {obj.city}, {obj.state} - {obj.zip_code}")
        lines.append("Country: India")

        plain_text = "\\n".join(lines).replace('"', '\\"').replace("'", "\\'")
        display_html = "<br/>".join(lines)

        return format_html(
            '<div style="background: #1E293B; color: #F8FAFC; padding: 14px 16px; border-radius: 8px; border: 1px solid #334155; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; font-size: 13px; line-height: 1.6; max-width: 560px;">'
            '<div style="margin-bottom: 12px; font-family: monospace; font-size: 12px; color: #E2E8F0;">{}</div>'
            '<button type="button" onclick="navigator.clipboard.writeText(\'{}\').then(function(){{ alert(\'Delivery address copied to clipboard!\'); }});" '
            'style="cursor: pointer; background: #BE185D; color: white; border: none; border-radius: 6px; padding: 7px 14px; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.2);">'
            '📋 Copy Full Address'
            '</button>'
            '</div>',
            format_html(display_html),
            plain_text,
        )
    formatted_address_with_copy.short_description = "Full Shipping Address (One-Click Copy)"

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
        if not obj or getattr(obj, 'total_amount', None) is None:
            return "₹0.00"
        return f"₹{float(obj.total_amount):.2f}"
    total_amount_display.short_description = 'Grand Total'

    def subtotal_display(self, obj):
        if not obj or getattr(obj, 'subtotal', None) is None:
            return "₹0.00"
        return f"₹{float(obj.subtotal):.2f}"
    subtotal_display.short_description = 'Subtotal'

    def shipping_fee_display(self, obj):
        if not obj or getattr(obj, 'shipping_fee', None) is None:
            return "₹0.00"
        return f"₹{float(obj.shipping_fee):.2f}"
    shipping_fee_display.short_description = 'Shipping Fee'

    def discount_display(self, obj):
        if not obj or getattr(obj, 'discount', None) is None:
            return "₹0.00"
        return f"₹{float(obj.discount):.2f}"
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

    def invoice_action(self, obj):
        url = f"/api/orders/{obj.order_number}/invoice/"
        return format_html(
            '<a href="{}" target="_blank" style="background-color: #552058; color: #FFFFFF; padding: 4px 10px; border-radius: 4px; font-weight: 600; font-size: 11px; text-decoration: none; display: inline-block;">📄 Invoice</a>',
            url,
        )
    invoice_action.short_description = 'Invoice'

    def invoice_link(self, obj):
        if obj.pk:
            url = f"/api/orders/{obj.order_number}/invoice/"
            return format_html(
                '<a href="{}" target="_blank" style="background-color: #552058; color: #FFFFFF; padding: 6px 14px; border-radius: 6px; font-weight: 600; font-size: 12px; text-decoration: none; display: inline-block;">📄 Download Order Invoice (PDF)</a>',
                url,
            )
        return "-"
    invoice_link.short_description = 'Order Invoice PDF'

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

    @admin.action(description="Export selected orders to formatted Excel (.xlsx)")
    def export_orders_to_excel_action(self, request, queryset):
        from django.http import HttpResponse
        from django.utils import timezone
        from reports.services import export_orders_to_excel

        excel_bytes = export_orders_to_excel(queryset)
        filename = f"sony_orders_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


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


# ReturnRequest is intentionally omitted from admin registration because returns/refunds are not supported (Policy: Only Damaged Product Exchange).
# class ReturnRequestAdmin is kept for compatibility with test imports.
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'order_link',
        'item_display',
        'customer_email',
        'reason',
        'status_badge',
        'created_at',
    ]
    list_filter = ['status', 'reason', 'created_at']
    search_fields = [
        'order__order_number',
        'user__email',
        'item__product_name',
        'item__product_sku',
    ]
    actions = [
        'approve_returns',
        'reject_returns',
        'mark_item_received_and_refund',
    ]
    readonly_fields = ['created_at', 'updated_at']

    def order_link(self, obj):
        return obj.order.order_number
    order_link.short_description = 'Order Number'

    def item_display(self, obj):
        return f"{obj.item.quantity}x {obj.item.product_name} ({obj.item.size}) - ₹{obj.item.line_total}"
    item_display.short_description = 'Returned Item'

    def customer_email(self, obj):
        return obj.user.email
    customer_email.short_description = 'Customer'

    def status_badge(self, obj):
        colors = {
            ReturnRequest.STATUS_REQUESTED: '#F59E0B',      # amber
            ReturnRequest.STATUS_APPROVED: '#3B82F6',       # blue
            ReturnRequest.STATUS_REJECTED: '#EF4444',       # red
            ReturnRequest.STATUS_ITEM_RECEIVED: '#8B5CF6',   # purple
            ReturnRequest.STATUS_REFUNDED: '#10B981',        # green
        }
        bg = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: #FFFFFF; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            bg,
            obj.status,
        )
    status_badge.short_description = 'Status'

    @admin.action(description="Approve selected return requests")
    def approve_returns(self, request, queryset):
        count = queryset.filter(status=ReturnRequest.STATUS_REQUESTED).update(status=ReturnRequest.STATUS_APPROVED)
        self.message_user(request, f"{count} return request(s) approved.")

    @admin.action(description="Reject selected return requests")
    def reject_returns(self, request, queryset):
        count = queryset.filter(status=ReturnRequest.STATUS_REQUESTED).update(status=ReturnRequest.STATUS_REJECTED)
        self.message_user(request, f"{count} return request(s) rejected.")

    @admin.action(description="Mark item received in warehouse and process refund (restores physical stock)")
    def mark_item_received_and_refund(self, request, queryset):
        from django.db import transaction
        from django.db.models import F
        from catalog.models import ProductVariant
        from payments.models import RefundRecord
        from payments.razorpay_client import dispatch_razorpay_refund

        processed = 0
        for return_req in queryset:
            if return_req.status not in (ReturnRequest.STATUS_REQUESTED, ReturnRequest.STATUS_APPROVED):
                continue

            with transaction.atomic():
                # 1. Restore physical inventory
                if return_req.item.variant_id:
                    ProductVariant.objects.filter(id=return_req.item.variant_id).update(
                        stock=F('stock') + return_req.item.quantity
                    )

                # 2. Trigger automated Razorpay refund if paid online
                order = return_req.order
                if order.payment_status in ('Paid', 'Refunded') and order.razorpay_payment_id:
                    idempotency_key = f"refund-return-{return_req.id}"
                    refund_amount_paise = int(return_req.item.line_total * 100)
                    try:
                        res = dispatch_razorpay_refund(
                            payment_id=order.razorpay_payment_id,
                            amount_paise=refund_amount_paise,
                            idempotency_key=idempotency_key,
                            reason=f"Return #{return_req.id} approved and received in warehouse",
                        )
                        RefundRecord.objects.create(
                            order=order,
                            idempotency_key=idempotency_key,
                            amount=return_req.item.line_total,
                            razorpay_refund_id=res.get('id'),
                            reason=f"Return #{return_req.id} approved and received",
                            status=RefundRecord.STATUS_PROCESSED,
                        )
                        return_req.status = ReturnRequest.STATUS_REFUNDED
                    except Exception as e:
                        RefundRecord.objects.create(
                            order=order,
                            idempotency_key=idempotency_key,
                            amount=return_req.item.line_total,
                            reason=f"Return #{return_req.id} approved and received",
                            status=RefundRecord.STATUS_FAILED_RETRYABLE,
                            error_message=str(e),
                        )
                        return_req.status = ReturnRequest.STATUS_ITEM_RECEIVED
                else:
                    return_req.status = ReturnRequest.STATUS_ITEM_RECEIVED

                return_req.save(update_fields=['status', 'updated_at'])
                processed += 1

        self.message_user(request, f"{processed} return request(s) processed with stock restored.")


@admin.register(ExchangeRequest)
class ExchangeRequestAdmin(admin.ModelAdmin):
    list_per_page = 25
    list_display = [
        'id',
        'order_link',
        'original_item_display',
        'reason_display',
        'proof_file_display',
        'customer_email',
        'status_badge',
        'exchange_code_display',
        'created_at',
    ]
    list_filter = ['status', 'reason', 'created_at']
    search_fields = [
        'order__order_number',
        'user__email',
        'item__product_name',
        'exchange_code',
    ]
    actions = [
        'approve_exchanges',
        'reject_exchanges',
    ]
    readonly_fields = ['exchange_code', 'proof_file_preview', 'created_at', 'updated_at']

    def order_link(self, obj):
        return obj.order.order_number
    order_link.short_description = 'Order Number'

    def original_item_display(self, obj):
        return f"{obj.item.quantity}x {obj.item.product_name} ({obj.item.size}) - ₹{obj.item.line_total}"
    original_item_display.short_description = 'Item for Exchange'

    def reason_display(self, obj):
        if obj.reason == 'other':
            return f"Other: {obj.other_reason or 'No details'}"
        return "Received damaged product"
    reason_display.short_description = 'Reason'

    def proof_file_display(self, obj):
        if obj.proof_file:
            return format_html(
                '<a href="{}" target="_blank" style="color: #552058; font-weight: bold;">View Proof ↗</a>',
                obj.proof_file.url,
            )
        return format_html('<span style="color: #9CA3AF;">No file</span>')
    proof_file_display.short_description = 'Damage Proof'

    def proof_file_preview(self, obj):
        if obj.proof_file:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height: 200px; border-radius: 8px;" /></a>',
                obj.proof_file.url,
                obj.proof_file.url,
            )
        return 'No proof file uploaded'
    proof_file_preview.short_description = 'Proof Preview'

    def exchange_code_display(self, obj):
        if obj.exchange_code:
            return format_html(
                '<code style="background: #F3E8FF; color: #552058; padding: 2px 6px; border-radius: 4px; font-weight: bold;">{}</code>',
                obj.exchange_code,
            )
        return '-'
    exchange_code_display.short_description = 'Exchange Voucher'

    def customer_email(self, obj):
        return obj.user.email
    customer_email.short_description = 'Customer'

    def status_badge(self, obj):
        colors = {
            ExchangeRequest.STATUS_REQUESTED: '#F59E0B',    # amber
            ExchangeRequest.STATUS_APPROVED: '#10B981',     # emerald/green
            ExchangeRequest.STATUS_REJECTED: '#EF4444',     # red
            ExchangeRequest.STATUS_DISPATCHED: '#3B82F6',   # blue
        }
        bg = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: #FFFFFF; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            bg,
            obj.status,
        )
    status_badge.short_description = 'Status'

    def save_model(self, request, obj, form, change):
        if obj.status == ExchangeRequest.STATUS_APPROVED and not obj.exchange_code:
            self._issue_exchange_coupon(obj)
        super().save_model(request, obj, form, change)

    def _issue_exchange_coupon(self, exchange_req):
        import uuid
        from django.utils import timezone
        code = f"EXC-{uuid.uuid4().hex[:8].upper()}"
        Coupon.objects.create(
            code=code,
            discount_type='fixed',
            value=exchange_req.item.line_total,
            min_order_value=exchange_req.item.line_total,  # same value or higher value only!
            valid_from=timezone.now(),
            valid_to=timezone.now() + timezone.timedelta(days=365),
            active=True,
            usage_limit=1,
            is_exchange_code=True,
            exchange_request=exchange_req,
            description=f"Exchange voucher for Order {exchange_req.order.order_number} ({exchange_req.item.product_name})",
        )
        exchange_req.exchange_code = code

    @admin.action(description="Approve selected exchange requests & issue store credit codes")
    def approve_exchanges(self, request, queryset):
        approved = 0
        for exc in queryset:
            if exc.status != ExchangeRequest.STATUS_APPROVED:
                if not exc.exchange_code:
                    self._issue_exchange_coupon(exc)
                exc.status = ExchangeRequest.STATUS_APPROVED
                exc.save(update_fields=['status', 'exchange_code', 'updated_at'])
                approved += 1
        self.message_user(request, f"{approved} exchange request(s) approved and single-use coupon code(s) generated.")

    @admin.action(description="Reject selected exchange requests")
    def reject_exchanges(self, request, queryset):
        count = queryset.filter(status=ExchangeRequest.STATUS_REQUESTED).update(status=ExchangeRequest.STATUS_REJECTED)
        self.message_user(request, f"{count} exchange request(s) rejected.")

    @admin.action(description="Mark replacement dispatched")
    def mark_exchange_dispatched(self, request, queryset):
        count = queryset.filter(status=ExchangeRequest.STATUS_APPROVED).update(status=ExchangeRequest.STATUS_DISPATCHED)
        self.message_user(request, f"{count} exchange(s) marked as dispatched.")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_per_page = 25
    list_display = [
        'code',
        'discount_badge',
        'min_order_value_display',
        'validity_display',
        'usage_display',
        'is_exchange_code',
        'active',
    ]
    list_filter = ['active', 'discount_type', 'is_exchange_code', 'valid_from', 'valid_to']
    search_fields = ['code', 'description']
    readonly_fields = ['uses_count', 'created_at', 'updated_at']
    actions = ['activate_coupons', 'deactivate_coupons']

    def discount_badge(self, obj):
        if not obj or getattr(obj, 'value', None) is None:
            text = "0% OFF"
        elif obj.discount_type == 'percentage':
            text = f"{obj.value:.0f}% OFF"
        else:
            text = f"₹{float(obj.value):.2f} OFF"
        color = "#552058" if not getattr(obj, 'is_exchange_code', False) else "#047857"
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            color,
            text,
        )
    discount_badge.short_description = 'Discount'

    def min_order_value_display(self, obj):
        if not obj or getattr(obj, 'min_order_value', None) is None:
            return "₹0.00"
        return f"₹{float(obj.min_order_value):.2f}"
    min_order_value_display.short_description = 'Min Order'

    def validity_display(self, obj):
        from django.utils import timezone
        now = timezone.now()
        is_expired = now > obj.valid_to
        color = "#DC2626" if is_expired else "#16A34A"
        return format_html(
            '<span style="color: {}; font-weight: 500;">{} to {}</span>',
            color,
            obj.valid_from.strftime('%d %b %Y'),
            obj.valid_to.strftime('%d %b %Y'),
        )
    validity_display.short_description = 'Validity Period'

    def usage_display(self, obj):
        return f"{obj.uses_count} / {obj.usage_limit}"
    usage_display.short_description = 'Uses'

    @admin.action(description="Activate selected coupons")
    def activate_coupons(self, request, queryset):
        count = queryset.update(active=True)
        self.message_user(request, f"{count} coupon(s) activated.")

    @admin.action(description="Deactivate selected coupons")
    def deactivate_coupons(self, request, queryset):
        count = queryset.update(active=False)
        self.message_user(request, f"{count} coupon(s) deactivated.")



