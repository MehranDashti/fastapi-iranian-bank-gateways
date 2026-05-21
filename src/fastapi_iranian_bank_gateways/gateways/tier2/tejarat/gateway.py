from typing import ClassVar

import httpx

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayConnectionError, GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from .config import TejaratConfig


class TejaratGateway(AbstractGateway):
    """Tejarat Bank (تجارت) — REST, redirect, POST callback."""

    gateway_slug: ClassVar[str] = "tejarat"
    config_class: ClassVar[type] = TejaratConfig
    callback_method: ClassVar[str] = "POST"

    def __init__(self, config: TejaratConfig) -> None:
        super().__init__(config)
        self.config: TejaratConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        payload = {
            "amount": request.amount,
            "callbackURL": request.callback_url,
            "invoiceNumber": request.order_id,
            "terminalNumber": self.config.terminal_id,
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.token_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        token = data.get("token")
        if token:
            return RedirectInitiateResponse(
                url=f"{self.config.gateway_url}?token={token}"
            )

        raise GatewayPaymentError(
            f"Tejarat token request failed: {data}",
            gateway=self.gateway_slug,
            raw=data,
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        token = str(raw.get("token", ""))
        order_id = str(raw.get("invoiceNumber", raw.get("_order_id", "")))
        status_code = str(raw.get("status", "-1"))

        if status_code not in ("0", "1"):
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=status_code,
                raw_response=raw,
            )

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.verify_url, json={
                    "token": token,
                    "terminalNumber": self.config.terminal_id,
                })
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        verify_status = str(data.get("status", "-1"))
        if verify_status in ("0", "1"):
            return PaymentResult(
                status=PaymentStatus.SUCCESS,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                reference_id=str(data.get("traceNumber", "")),
                card_number=data.get("maskedCardNumber"),
                raw_response={**raw, **data},
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            error_code=verify_status,
            raw_response={**raw, **data},
        )
