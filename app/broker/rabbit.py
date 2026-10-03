from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.broker.topology import (
    DLX_EXCHANGE,
    PAYMENTS_DLQ_RK,
    PAYMENTS_EXCHANGE,
    PAYMENTS_NEW_QUEUE,
    PAYMENTS_NEW_RK,
    RETRY_EXCHANGE,
)
from app.core.config import settings

broker = RabbitBroker(settings.rabbitmq_url)

payments_exchange = RabbitExchange(PAYMENTS_EXCHANGE, durable=True, type=ExchangeType.DIRECT)
retry_exchange = RabbitExchange(RETRY_EXCHANGE, durable=True, type=ExchangeType.DIRECT)
dlx_exchange = RabbitExchange(DLX_EXCHANGE, durable=True, type=ExchangeType.DIRECT)

payments_new_queue = RabbitQueue(
    PAYMENTS_NEW_QUEUE,
    durable=True,
    routing_key=PAYMENTS_NEW_RK,
    arguments={
        "x-queue-type": "classic",
        "x-dead-letter-exchange": DLX_EXCHANGE,
        "x-dead-letter-routing-key": PAYMENTS_DLQ_RK,
    },
)
