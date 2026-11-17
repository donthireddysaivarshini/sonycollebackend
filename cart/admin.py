from django.contrib import admin
from .models import Cart, CartItem, StockReservation


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ['variant', 'quantity', 'unit_price', 'line_total', 'created_at']
    readonly_fields = ['unit_price', 'line_total', 'created_at']

    def unit_price(self, obj):
        return f"₹{obj.unit_price:.2f}"

    def line_total(self, obj):
        return f"₹{obj.line_total:.2f}"


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'owner_display', 'items_count', 'subtotal_display', 'grand_total_display', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__email', 'session_key']
    inlines = [CartItemInline]
    readonly_fields = ['items_count', 'subtotal_display', 'shipping_fee_display', 'tax_amount_display', 'grand_total_display', 'created_at', 'updated_at']

    def owner_display(self, obj):
        return obj.user.email if obj.user else f"Guest ({obj.session_key[:8]}...)" if obj.session_key else "Anonymous"
    owner_display.short_description = 'Customer / Session'

    def subtotal_display(self, obj):
        return f"₹{obj.subtotal:.2f}"
    subtotal_display.short_description = 'Subtotal'

    def shipping_fee_display(self, obj):
        return f"₹{obj.shipping_fee:.2f}"
    shipping_fee_display.short_description = 'Shipping Fee'

    def tax_amount_display(self, obj):
        return f"₹{obj.tax_amount:.2f}"
    tax_amount_display.short_description = 'Tax'

    def grand_total_display(self, obj):
        return f"₹{obj.grand_total:.2f}"
    grand_total_display.short_description = 'Grand Total'


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display = ['id', 'variant', 'quantity', 'user_or_session', 'order_number', 'status', 'expires_at', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['variant__sku', 'user__email', 'session_key', 'order_number']
    readonly_fields = ['created_at']
    actions = ['release_selected_holds', 'expire_selected_holds']

    def user_or_session(self, obj):
        if obj.user:
            return obj.user.email
        return f"Session: {obj.session_key[:8]}..." if obj.session_key else "None"
    user_or_session.short_description = 'Hold Owner'

    @admin.action(description="Release selected active holds back to available stock")
    def release_selected_holds(self, request, queryset):
        count = 0
        for hold in queryset.filter(status=StockReservation.STATUS_ACTIVE):
            hold.release()
            count += 1
        self.message_user(request, f"Successfully released {count} hold(s).")

    @admin.action(description="Expire selected active holds and restore stock")
    def expire_selected_holds(self, request, queryset):
        count = 0
        for hold in queryset.filter(status=StockReservation.STATUS_ACTIVE):
            hold.expire()
            count += 1
        self.message_user(request, f"Successfully expired {count} hold(s).")

