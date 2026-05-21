from typing import ClassVar

import httpx

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayConnectionError, GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from .config import VandarConfig


class VandarGateway(AbstractGateway):
    """Vandar — REST/JSON, redirect, POST callback."""

    gateway_slug: ClassVar[str] = "vandar"
    config_class: ClassVar[type] = VandarConfig
    callback_method: ClassVar[str] = "POST"

    def __init__(self, config: VandarConfig) -> None:
        super().__init__(config)
        self.config: VandarConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        payload = {
            "api_key": self.config.api_key,
            "amount": request.amount,
            "callback_url": request.callback_url,
            "factorNumber": request.order_id,
            "mobile_number": request.mobile or "",
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
            f"Vandar initiation failed: {data}",
            gateway=self.gateway_slug,
            code=str(data.get("errors", "")),
            raw=data,
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        token = str(raw.get("token", ""))
        order_id = str(raw.get("factorNumber", raw.get("_order_id", "")))
        payment_status = str(raw.get("payment_status", ""))

        if payment_status != "DONE":
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=payment_status,
                raw_response=raw,
            )

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.verify_url, json={
                    "api_key": self.config.api_key,
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
                reference_id=str(data.get("transId", "")),
                card_number=data.get("cardNumber"),
                raw_response=data,
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            error_code=str(data.get("errors", "")),
            raw_response=data,
        )
