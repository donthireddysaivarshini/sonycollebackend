from django.urls import path
from .views import (
    OrderCancelView,
    OrderCheckoutView,
    OrderCreateView,
    OrderDetailView,
    OrderListView,
)

app_name = 'orders'

urlpatterns = [
    path('', OrderListView.as_view(), name='order_list'),
    path('checkout/', OrderCheckoutView.as_view(), name='order_checkout'),
    path('create/', OrderCreateView.as_view(), name='order_create'),
    path('<str:order_number>/', OrderDetailView.as_view(), name='order_detail'),
    path('<str:order_number>/cancel/', OrderCancelView.as_view(), name='order_cancel'),
]

