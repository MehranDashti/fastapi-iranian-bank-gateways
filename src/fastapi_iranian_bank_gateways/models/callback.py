from typing import Any

from pydantic import BaseModel, Field

from .enums import PaymentStatus


class BankCallbackData(BaseModel):
    model_config = {"extra": "allow"}

    gateway_slug: str
    raw: dict[str, Any]


class PaymentResult(BaseModel):
    status: PaymentStatus
    gateway_slug: str
    order_id: str
    transaction_id: str | None = None
    reference_id: str | None = None
    amount: int | None = None
    card_number: str | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
