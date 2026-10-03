from uuid import UUID

from pydantic import BaseModel


class PaymentNewEvent(BaseModel):
    payment_id: UUID
