from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ApiKeyDep, IdempotencyKeyDep
from app.db.session import get_db
from app.schemas.payment import PaymentCreate, PaymentCreated, PaymentDetail
from app.services.exceptions import IdempotencyConflictError
from app.services.payments import create_payment, get_payment

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=PaymentCreated)
async def create_payment_endpoint(
    body: PaymentCreate,
    db: DbDep,
    _: ApiKeyDep,
    idempotency_key: IdempotencyKeyDep,
) -> PaymentCreated:
    try:
        payment = await create_payment(db, body, idempotency_key)
    except IdempotencyConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency-Key already used with a different payload",
        ) from None
    return PaymentCreated(payment_id=payment.id, status=payment.status, created_at=payment.created_at)


@router.get("/{payment_id}", response_model=PaymentDetail)
async def get_payment_endpoint(payment_id: UUID, db: DbDep, _: ApiKeyDep) -> PaymentDetail:
    payment = await get_payment(db, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return PaymentDetail(
        payment_id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        description=payment.description,
        metadata=payment.metadata_ or {},
        status=payment.status,
        idempotency_key=payment.idempotency_key,
        webhook_url=payment.webhook_url,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )
