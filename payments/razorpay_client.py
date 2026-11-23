import hashlib
import hmac
import logging
from typing import Any

from django.conf import settings
import razorpay

logger = logging.getLogger(__name__)


def get_razorpay_client() -> razorpay.Client | None:
    """
    Returns an initialized Razorpay Client instance using configured credentials.
    """
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
    if not key_id or not key_secret:
        return None
    return razorpay.Client(auth=(key_id, key_secret))


def create_razorpay_order(amount_paise: int, receipt: str, currency: str = "INR") -> dict[str, Any]:
    """
    Creates a server-side order with Razorpay in paise.
    Simulates response if running in test environment or with placeholder credentials.
    """
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    if key_id.startswith('rzp_test_placeholder') or 'your_razorpay_key' in key_id or getattr(settings, 'RAZORPAY_MOCK_DISPATCH', False):
        return {
            'id': f"order_sim_{receipt}",
            'amount': amount_paise,
            'currency': currency,
            'receipt': receipt,
            'status': 'created',
        }

    client = get_razorpay_client()
    data = {
        'amount': amount_paise,
        'currency': currency,
        'receipt': receipt,
        'payment_capture': 1,
    }

    if client:
        try:
            return client.order.create(data=data)
        except Exception as e:
            logger.warning(f"Razorpay API call failed, generating simulated order for dev/test: {e}")

    # Fallback / dev / test simulation
    return {
        'id': f"order_sim_{receipt}",
        'amount': amount_paise,
        'currency': currency,
        'receipt': receipt,
        'status': 'created',
    }


def compute_payment_signature(razorpay_order_id: str, razorpay_payment_id: str, secret: str = None) -> str:
    """
    Computes expected HMAC-SHA256 signature for Razorpay payment callback verification.
    """
    if secret is None:
        secret = getattr(settings, 'RAZORPAY_KEY_SECRET', 'placeholder_secret')
    message = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
    return hmac.new(secret.encode('utf-8'), message, hashlib.sha256).hexdigest()


def verify_payment_signature(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
    """
    Verifies that razorpay_signature is a valid HMAC-SHA256 of order_id|payment_id.
    """
    secret = getattr(settings, 'RAZORPAY_KEY_SECRET', 'placeholder_secret')
    expected_sig = compute_payment_signature(razorpay_order_id, razorpay_payment_id, secret)
    return hmac.compare_digest(expected_sig, razorpay_signature)


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Verifies X-Razorpay-Signature from webhook notification.
    """
    secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', 'placeholder_webhook_secret')
    expected_sig = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, signature_header)


def dispatch_razorpay_refund(
    payment_id: str,
    amount_paise: int,
    idempotency_key: str,
    reason: str = '',
) -> dict[str, Any]:
    """
    Submits a refund request to Razorpay with an idempotency note.
    Simulates response if running in test environment or with placeholder credentials.
    """
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    if key_id.startswith('rzp_test_placeholder') or 'your_razorpay_key' in key_id or getattr(settings, 'RAZORPAY_MOCK_DISPATCH', False):
        return {
            'id': f"rfnd_sim_{idempotency_key[:12]}",
            'payment_id': payment_id,
            'amount': amount_paise,
            'status': 'processed',
        }

    client = get_razorpay_client()
    data = {
        'amount': amount_paise,
        'speed': 'normal',
        'notes': {
            'idempotency_key': idempotency_key,
            'reason': reason,
        },
    }

    if client:
        try:
            return client.payment.refund(payment_id, data)
        except Exception as e:
            logger.error(f"Razorpay refund dispatch failed for {payment_id}: {e}")
            raise e

    return {
        'id': f"rfnd_sim_{idempotency_key[:12]}",
        'payment_id': payment_id,
        'amount': amount_paise,
        'status': 'processed',
    }

