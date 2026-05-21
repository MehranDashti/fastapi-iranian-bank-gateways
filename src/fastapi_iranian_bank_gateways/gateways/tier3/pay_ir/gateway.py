from typing import ClassVar

import httpx

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayConnectionError, GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from .config import PayIrConfig


class PayIrGateway(AbstractGateway):
    """Pay.ir — REST/JSON, redirect, GET callback."""

    gateway_slug: ClassVar[str] = "pay_ir"
    config_class: ClassVar[type] = PayIrConfig
    callback_method: ClassVar[str] = "GET"

    def __init__(self, config: PayIrConfig) -> None:
        super().__init__(config)
        self.config: PayIrConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        payload = {
            "api": self.config.api,
            "amount": request.amount,
            "redirect": request.callback_url,
            "factorNumber": request.order_id,
            "mobile": request.mobile or "",
            "description": request.description or "",
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.send_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        if data.get("status") == 1:
            token = data["token"]
            return RedirectInitiateResponse(url=f"{self.config.gateway_url}{token}")

        raise GatewayPaymentError(
            f"Pay.ir initiation failed: {data}",
            gateway=self.gateway_slug,
            code=str(data.get("errorCode", "")),
            raw=data,
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        token = str(raw.get("token", ""))
        order_id = str(raw.get("factorNumber", raw.get("_order_id", "")))
        cb_status = str(raw.get("status", "0"))

        if cb_status != "1":
            return PaymentResult(
                status=PaymentStatus.CANCELLED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                raw_response=raw,
            )

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.verify_url, json={
                    "api": self.config.api,
                    "token": token,
                })
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        if data.get("status") == 1:
            return PaymentResult(
                status=PaymentStatus.SUCCESS,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                transaction_id=str(data.get("transId", "")),
                card_number=data.get("cardNumber"),
                raw_response=data,
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            error_code=str(data.get("errorCode", "")),
            raw_response=data,
        )
