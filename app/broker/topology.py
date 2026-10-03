from aio_pika import ExchangeType, connect_robust
from aio_pika.abc import AbstractChannel

PAYMENTS_EXCHANGE = "payments"
RETRY_EXCHANGE = "payments.retry"
DLX_EXCHANGE = "payments.dlx"

PAYMENTS_NEW_QUEUE = "payments.new"
PAYMENTS_NEW_RK = "payments.new"
PAYMENTS_DLQ = "payments.dlq"
PAYMENTS_DLQ_RK = "payments.dlq"


RETRY_DELAYS_MS = {
    1: 1000,
    2: 2000,
}


async def declare_topology(url: str) -> None:
    connection = await connect_robust(url)
    async with connection:
        channel = await connection.channel()
        await _declare(channel)


async def _declare(channel: AbstractChannel) -> None:
    payments_ex = await channel.declare_exchange(PAYMENTS_EXCHANGE, ExchangeType.DIRECT, durable=True)
    retry_ex = await channel.declare_exchange(RETRY_EXCHANGE, ExchangeType.DIRECT, durable=True)
    dlx_ex = await channel.declare_exchange(DLX_EXCHANGE, ExchangeType.DIRECT, durable=True)

    new_queue = await channel.declare_queue(
        PAYMENTS_NEW_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "classic",
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": PAYMENTS_DLQ_RK,
        },
    )
    await new_queue.bind(payments_ex, routing_key=PAYMENTS_NEW_RK)

    for delay_s, ttl_ms in RETRY_DELAYS_MS.items():
        routing_key = f"retry.{delay_s}"
        queue = await channel.declare_queue(
            f"payments.retry.{delay_s}",
            durable=True,
            arguments={
                "x-message-ttl": ttl_ms,
                "x-dead-letter-exchange": PAYMENTS_EXCHANGE,
                "x-dead-letter-routing-key": PAYMENTS_NEW_RK,
            },
        )
        await queue.bind(retry_ex, routing_key=routing_key)

    dlq = await channel.declare_queue(PAYMENTS_DLQ, durable=True)
    await dlq.bind(dlx_ex, routing_key=PAYMENTS_DLQ_RK)
