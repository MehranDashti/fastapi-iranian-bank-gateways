from typing import ClassVar

import httpx

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayConnectionError, GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from .config import NextPayConfig


class NextPayGateway(AbstractGateway):
    """NextPay (نکست پی) — REST/JSON, redirect, GET callback."""

    gateway_slug: ClassVar[str] = "nextpay"
    config_class: ClassVar[type] = NextPayConfig
    callback_method: ClassVar[str] = "GET"

    def __init__(self, config: NextPayConfig) -> None:
        super().__init__(config)
        self.config: NextPayConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        payload = {
            "api_key": self.config.api_key,
            "order_id": request.order_id,
            "amount": request.amount,
            "callback_uri": request.callback_url,
            "customer_phone": request.mobile or "",
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.token_url, data=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        if data.get("code") == -1:
            trans_id = data["trans_id"]
            return RedirectInitiateResponse(
                url=f"{self.config.gateway_url}{trans_id}"
            )

        raise GatewayPaymentError(
            f"NextPay initiation failed: code={data.get('code')}",
            gateway=self.gateway_slug,
            code=str(data.get("code", "")),
            raw=data,
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        trans_id = str(raw.get("trans_id", ""))
        order_id = str(raw.get("order_id", raw.get("_order_id", "")))
        amount = raw.get("_amount") or raw.get("amount")

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.verify_url, data={
                    "api_key": self.config.api_key,
                    "trans_id": trans_id,
                    "amount": int(amount) if amount else 0,
                })
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        code = data.get("code")
        if code == -90:
            status = PaymentStatus.SUCCESS
        elif code == 0:
            status = PaymentStatus.DUPLICATE
        else:
            status = PaymentStatus.FAILED

        return PaymentResult(
            status=status,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            transaction_id=trans_id,
            reference_id=str(data.get("Shaparak_Ref_Id", "")),
            card_number=data.get("card_holder"),
            raw_response=data,
            error_code=None if status != PaymentStatus.FAILED else str(code),
        )
