from django.urls import path
from .views import OrderCancelView, OrderCreateView, OrderDetailView, OrderListView

app_name = 'orders'

urlpatterns = [
    path('', OrderListView.as_view(), name='order_list'),
    path('create/', OrderCreateView.as_view(), name='order_create'),
    path('<str:order_number>/', OrderDetailView.as_view(), name='order_detail'),
    path('<str:order_number>/cancel/', OrderCancelView.as_view(), name='order_cancel'),
]

