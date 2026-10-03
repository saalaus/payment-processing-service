import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.broker.rabbit import broker, payments_exchange
from app.broker.topology import PAYMENTS_NEW_RK, declare_topology
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.outbox import OutboxEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("outbox-publisher")


async def publish_one() -> bool:
    async with SessionLocal() as session:
        async with session.begin():
            stmt = (
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            event = await session.scalar(stmt)
            if event is None:
                return False

            await broker.publish(
                event.payload,
                exchange=payments_exchange,
                routing_key=PAYMENTS_NEW_RK,
                persist=True,
            )
            event.published_at = datetime.now(UTC)
            logger.info("Published outbox event %s (%s)", event.id, event.event_type)
            return True


async def publish_batch() -> int:
    published = 0
    for _ in range(settings.outbox_batch_size):
        if not await publish_one():
            break
        published += 1
    return published


async def run() -> None:
    await declare_topology(settings.rabbitmq_url)
    await broker.start()
    logger.info("Outbox publisher started")
    try:
        while True:
            try:
                published = await publish_batch()
            except Exception:
                logger.exception("Failed to publish outbox batch")
                published = 0
            if published == 0:
                await asyncio.sleep(settings.outbox_poll_interval_seconds)
    finally:
        await broker.stop()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
