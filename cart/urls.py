from django.urls import path
from .views import (
    CartClearView,
    CartItemCreateView,
    CartItemDetailView,
    CartMergeView,
    CartValidateView,
    CartView,
    CheckoutSummaryView,
)

app_name = 'cart'

urlpatterns = [
    path('', CartView.as_view(), name='cart_detail'),
    path('items/', CartItemCreateView.as_view(), name='cart_item_create'),
    path('items/<int:item_id>/', CartItemDetailView.as_view(), name='cart_item_detail'),
    path('clear/', CartClearView.as_view(), name='cart_clear'),
    path('merge/', CartMergeView.as_view(), name='cart_merge'),
    path('validate/', CartValidateView.as_view(), name='cart_validate'),
    path('checkout-summary/', CheckoutSummaryView.as_view(), name='cart_checkout_summary'),
]

