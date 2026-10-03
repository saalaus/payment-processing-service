from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import OutboxEvent
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentCreate
from app.services.exceptions import IdempotencyConflictError

PAYMENTS_NEW_EVENT = "payments.new"


def _payloads_match(payment: Payment, data: PaymentCreate) -> bool:
    amount = Decimal(payment.amount).quantize(Decimal("0.01"))
    incoming = Decimal(data.amount).quantize(Decimal("0.01"))
    return (
        amount == incoming
        and payment.currency == data.currency
        and payment.description == data.description
        and (payment.metadata_ or {}) == (data.metadata or {})
        and payment.webhook_url.rstrip("/") == str(data.webhook_url).rstrip("/")
    )


async def _get_by_idempotency_key(session: AsyncSession, key: str) -> Payment | None:
    return await session.scalar(select(Payment).where(Payment.idempotency_key == key))


async def create_payment(
    session: AsyncSession,
    data: PaymentCreate,
    idempotency_key: str,
) -> Payment:
    existing = await _get_by_idempotency_key(session, idempotency_key)
    if existing is not None:
        if not _payloads_match(existing, data):
            raise IdempotencyConflictError
        return existing

    payment = Payment(
        amount=Decimal(data.amount),
        currency=data.currency,
        description=data.description,
        metadata_=data.metadata or {},
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
        webhook_url=str(data.webhook_url),
    )

    try:
        async with session.begin_nested():
            session.add(payment)
            await session.flush()
            session.add(
                OutboxEvent(
                    event_type=PAYMENTS_NEW_EVENT,
                    payload={"payment_id": str(payment.id)},
                )
            )
            await session.flush()
    except IntegrityError:
        if payment in session:
            session.expunge(payment)
        existing = await _get_by_idempotency_key(session, idempotency_key)
        if existing is None:
            raise
        if not _payloads_match(existing, data):
            raise IdempotencyConflictError
        return existing

    await session.refresh(payment)
    return payment


async def get_payment(session: AsyncSession, payment_id: UUID) -> Payment | None:
    return await session.get(Payment, payment_id)
