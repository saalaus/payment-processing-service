import asyncio
import logging
import random
from datetime import UTC, datetime

from faststream import FastStream, Header
from sqlalchemy import select

from app.broker.rabbit import broker, dlx_exchange, payments_exchange, payments_new_queue, retry_exchange
from app.broker.topology import PAYMENTS_DLQ_RK, declare_topology
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.payment import Payment, PaymentStatus
from app.schemas.events import PaymentNewEvent
from app.services.webhook import WebhookDeliveryError, send_webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("consumer")

RETRY_COUNT_HEADER = "x-retry-count"
RETRY_ROUTING = {1: "retry.1", 2: "retry.2"}

app = FastStream(broker)


async def emulate_gateway() -> bool:
    delay = random.uniform(settings.gateway_delay_min_seconds, settings.gateway_delay_max_seconds)
    await asyncio.sleep(delay)
    return random.random() < settings.payment_success_rate


async def process_payment(event: PaymentNewEvent) -> None:
    async with SessionLocal() as session:
        payment = await session.scalar(select(Payment).where(Payment.id == event.payment_id))
        if payment is None:
            raise RuntimeError(f"Payment {event.payment_id} not found")
        if payment.status != PaymentStatus.PENDING:
            logger.info("Payment %s already in terminal status %s", payment.id, payment.status.value)
            await send_webhook(payment)
            return

    succeeded = await emulate_gateway()

    async with SessionLocal() as session:
        payment = await session.scalar(select(Payment).where(Payment.id == event.payment_id))
        if payment is None:
            raise RuntimeError(f"Payment {event.payment_id} not found")
        if payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.SUCCEEDED if succeeded else PaymentStatus.FAILED
            payment.processed_at = datetime.now(UTC)
            await session.commit()
            logger.info("Payment %s processed: %s", payment.id, payment.status.value)
        else:
            logger.info("Payment %s already in terminal status %s", payment.id, payment.status.value)
        await send_webhook(payment)


async def retry_or_dlq(event: PaymentNewEvent, retry_count: int) -> None:
    next_attempt = retry_count + 1
    body = event.model_dump(mode="json")
    headers = {RETRY_COUNT_HEADER: next_attempt}

    if next_attempt >= settings.max_process_attempts:
        logger.error("Moving payment %s to DLQ after %s attempts", event.payment_id, next_attempt)
        await broker.publish(
            body,
            exchange=dlx_exchange,
            routing_key=PAYMENTS_DLQ_RK,
            persist=True,
            headers=headers,
        )
        return

    delay_key = RETRY_ROUTING[next_attempt]
    logger.warning(
        "Scheduling retry %s for payment %s via %s",
        next_attempt,
        event.payment_id,
        delay_key,
    )
    await broker.publish(
        body,
        exchange=retry_exchange,
        routing_key=delay_key,
        persist=True,
        headers=headers,
    )


@broker.subscriber(payments_new_queue, payments_exchange)
async def handle_payment_new(
    event: PaymentNewEvent,
    x_retry_count: int = Header(RETRY_COUNT_HEADER, default=0),
) -> None:
    try:
        retry_count = int(x_retry_count)
    except (TypeError, ValueError):
        retry_count = 0
    try:
        await process_payment(event)
    except WebhookDeliveryError:
        logger.exception("Webhook failed for payment %s", event.payment_id)
        await retry_or_dlq(event, retry_count)
    except Exception:
        logger.exception("Failed to process payment %s", event.payment_id)
        await retry_or_dlq(event, retry_count)


@app.on_startup
async def on_startup() -> None:
    await declare_topology(settings.rabbitmq_url)
    logger.info("RabbitMQ topology declared")


async def main() -> None:
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
