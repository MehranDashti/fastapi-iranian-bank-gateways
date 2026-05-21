from typing import Any, Literal

from pydantic import BaseModel, Field

from .enums import Currency


class PaymentRequest(BaseModel):
    order_id: str
    amount: int = Field(..., gt=0, description="Amount in Rials (IRR)")
    currency: Currency = Currency.IRR
    callback_url: str
    mobile: str | None = None
    email: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FormInitiateResponse(BaseModel):
    type: Literal["form"] = "form"
    html: str


class RedirectInitiateResponse(BaseModel):
    type: Literal["redirect"] = "redirect"
    url: str


InitiateResponse = FormInitiateResponse | RedirectInitiateResponse
