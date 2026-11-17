from rest_framework import serializers
from .models import PaymentTransaction, RefundRecord


class RazorpayVerifySerializer(serializers.Serializer):
    """
    Validates payment callback payload submitted by frontend Razorpay checkout modal.
    """

    razorpay_order_id = serializers.CharField(required=True, max_length=100)
    razorpay_payment_id = serializers.CharField(required=True, max_length=100)
    razorpay_signature = serializers.CharField(required=True, max_length=255)


class PaymentTransactionSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    amount = serializers.SerializerMethodField()

    class Meta:
        model = PaymentTransaction
        fields = [
            'id',
            'order_number',
            'gateway',
            'gateway_order_id',
            'gateway_payment_id',
            'amount',
            'status',
            'created_at',
        ]

    def get_amount(self, obj) -> str:
        return f"{obj.amount:.2f}"


class RefundRecordSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    amount = serializers.SerializerMethodField()

    class Meta:
        model = RefundRecord
        fields = [
            'id',
            'order_number',
            'idempotency_key',
            'amount',
            'razorpay_refund_id',
            'reason',
            'status',
            'retry_count',
            'created_at',
        ]

    def get_amount(self, obj) -> str:
        return f"{obj.amount:.2f}"

