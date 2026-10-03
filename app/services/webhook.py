import asyncio
import logging
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import settings
from app.models.payment import Payment

logger = logging.getLogger(__name__)


class WebhookDeliveryError(Exception):
    """Webhook could not be delivered after all retries."""


def _webhook_payload(payment: Payment) -> dict[str, Any]:
    amount = payment.amount
    if isinstance(amount, Decimal):
        amount_value: str | Decimal = format(amount, "f")
    else:
        amount_value = amount
    return {
        "payment_id": str(payment.id),
        "status": payment.status.value,
        "amount": amount_value,
        "currency": payment.currency.value,
        "processed_at": payment.processed_at.isoformat() if payment.processed_at else None,
    }


async def send_webhook(payment: Payment) -> None:
    payload = _webhook_payload(payment)
    delay = 1.0
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
        for attempt in range(1, settings.webhook_max_attempts + 1):
            try:
                response = await client.post(payment.webhook_url, json=payload)
                response.raise_for_status()
                logger.info("Webhook delivered for payment %s", payment.id)
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Webhook attempt %s/%s failed for payment %s: %s",
                    attempt,
                    settings.webhook_max_attempts,
                    payment.id,
                    exc,
                )
                if attempt < settings.webhook_max_attempts:
                    await asyncio.sleep(delay)
                    delay *= 2

    raise WebhookDeliveryError(f"Failed to deliver webhook for payment {payment.id}") from last_error
