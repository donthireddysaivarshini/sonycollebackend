from django.urls import path
from .views import (
    PaymentTransactionListView,
    RazorpayVerifyView,
    RazorpayWebhookView,
    RefundRecordListView,
)

app_name = 'payments'

urlpatterns = [
    path('razorpay/verify/', RazorpayVerifyView.as_view(), name='razorpay_verify'),
    path('razorpay/webhook/', RazorpayWebhookView.as_view(), name='razorpay_webhook'),
    path('transactions/', PaymentTransactionListView.as_view(), name='transaction_list'),
    path('refunds/', RefundRecordListView.as_view(), name='refund_list'),
]

