from django.urls import path
from .views import (
    CustomerExchangeListView,
    CustomerReturnListView,
    OrderCancelView,
    OrderCheckoutView,
    CouponValidateView,
    OrderCreateView,
    OrderDetailView,
    OrderExchangeRequestView,
    OrderListView,
    OrderReturnRequestView,
)
from reports.views import OrderInvoiceDownloadView

app_name = 'orders'

urlpatterns = [
    path('', OrderListView.as_view(), name='order_list'),
    path('checkout/', OrderCheckoutView.as_view(), name='order_checkout'),
    path('coupons/validate/', CouponValidateView.as_view(), name='coupon_validate'),
    path('create/', OrderCreateView.as_view(), name='order_create'),
    path('returns/', CustomerReturnListView.as_view(), name='customer_returns'),
    path('exchanges/', CustomerExchangeListView.as_view(), name='customer_exchanges'),
    path('<str:order_number>/', OrderDetailView.as_view(), name='order_detail'),
    path('<str:order_number>/cancel/', OrderCancelView.as_view(), name='order_cancel'),
    path('<str:order_number>/returns/', OrderReturnRequestView.as_view(), name='order_returns'),
    path('<str:order_number>/exchanges/', OrderExchangeRequestView.as_view(), name='order_exchanges'),
    path('<str:order_number>/invoice/', OrderInvoiceDownloadView.as_view(), name='order_invoice'),
]

