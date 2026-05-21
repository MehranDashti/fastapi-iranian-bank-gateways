from typing import ClassVar

import httpx

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayConnectionError, GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from .config import PayPingConfig


class PayPingGateway(AbstractGateway):
    """PayPing — REST/JSON, redirect, GET callback."""

    gateway_slug: ClassVar[str] = "payping"
    config_class: ClassVar[type] = PayPingConfig
    callback_method: ClassVar[str] = "GET"

    def __init__(self, config: PayPingConfig) -> None:
        super().__init__(config)
        self.config: PayPingConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        payload = {
            "amount": request.amount // 10,  # PayPing uses Tomans
            "returnUrl": request.callback_url,
            "payerIdentity": request.mobile or request.email or "",
            "description": request.description or f"Order {request.order_id}",
            "clientRefId": request.order_id,
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(
                    self.config.request_url,
                    json=payload,
                    headers=self.config._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        code = data.get("code")
        if code:
            return RedirectInitiateResponse(url=f"{self.config.gateway_url}{code}")

        raise GatewayPaymentError(
            f"PayPing initiation failed: {data}",
            gateway=self.gateway_slug,
            raw=data,
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        ref_id = str(raw.get("refid", ""))
        order_id = str(raw.get("clientrefid") or callback_data.order_id or raw.get("_order_id", ""))
        amount = callback_data.amount or raw.get("_amount")

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(
                    self.config.verify_url,
                    json={
                        "refId": ref_id,
                        "amount": int(amount) // 10 if amount else 0,  # Tomans
                    },
                    headers=self.config._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        # PayPing returns 200 OK with cardNumber on success
        card = data.get("cardNumber")
        if card is not None:
            return PaymentResult(
                status=PaymentStatus.SUCCESS,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                reference_id=ref_id,
                card_number=card,
                raw_response=data,
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            raw_response=data,
        )
