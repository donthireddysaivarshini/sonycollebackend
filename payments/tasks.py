import logging
from .models import RefundRecord
from .razorpay_client import dispatch_razorpay_refund

logger = logging.getLogger(__name__)


def process_pending_refund_records() -> int:
    """
    Background recoverable task processing pending and retryable customer refunds.
    Enforces idempotency and tracks retry attempts up to 5 times.
    """
    eligible_refunds = RefundRecord.objects.filter(
        status__in=[RefundRecord.STATUS_PENDING, RefundRecord.STATUS_FAILED_RETRYABLE],
        retry_count__lt=5,
    ).select_related('order', 'payment')

    processed_count = 0

    for refund in eligible_refunds:
        payment_id = (
            refund.payment.gateway_payment_id
            if refund.payment and refund.payment.gateway_payment_id
            else refund.order.razorpay_payment_id
        )

        if not payment_id:
            refund.status = RefundRecord.STATUS_FAILED_PERMANENT
            refund.error_message = "No valid gateway payment ID found for order."
            refund.save(update_fields=['status', 'error_message', 'updated_at'])
            continue

        try:
            amount_paise = int(refund.amount * 100)
            result = dispatch_razorpay_refund(
                payment_id=payment_id,
                amount_paise=amount_paise,
                idempotency_key=refund.idempotency_key,
                reason=refund.reason,
            )
            refund.razorpay_refund_id = result.get('id')
            refund.status = RefundRecord.STATUS_PROCESSED
            refund.error_message = None
            refund.save(update_fields=['razorpay_refund_id', 'status', 'error_message', 'updated_at'])
            processed_count += 1
        except Exception as e:
            refund.retry_count += 1
            if refund.retry_count >= 5:
                refund.status = RefundRecord.STATUS_FAILED_PERMANENT
            else:
                refund.status = RefundRecord.STATUS_FAILED_RETRYABLE
            refund.error_message = str(e)
            refund.save(update_fields=['retry_count', 'status', 'error_message', 'updated_at'])
            logger.warning(f"Refund #{refund.id} retry {refund.retry_count} failed: {e}")

    return processed_count

