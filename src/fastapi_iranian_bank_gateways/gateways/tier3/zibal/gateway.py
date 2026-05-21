from typing import ClassVar

import httpx

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayConnectionError, GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from .config import ZibalConfig


class ZibalGateway(AbstractGateway):
    """Zibal (زیبال) — REST/JSON, redirect, GET callback."""

    gateway_slug: ClassVar[str] = "zibal"
    config_class: ClassVar[type] = ZibalConfig
    callback_method: ClassVar[str] = "GET"

    def __init__(self, config: ZibalConfig) -> None:
        super().__init__(config)
        self.config: ZibalConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        payload = {
            "merchant": self.config.merchant,
            "amount": request.amount,
            "callbackUrl": request.callback_url,
            "orderId": request.order_id,
            "description": request.description or "",
            "mobile": request.mobile or "",
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.request_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        if data.get("result") == 100:
            track_id = data["trackId"]
            return RedirectInitiateResponse(url=f"{self.config.start_url}{track_id}")

        raise GatewayPaymentError(
            f"Zibal initiation failed: result={data.get('result')}",
            gateway=self.gateway_slug,
            code=str(data.get("result", "")),
            raw=data,
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        track_id = str(raw.get("trackId", ""))
        order_id = str(raw.get("orderId", raw.get("_order_id", "")))
        success = str(raw.get("success", "0"))

        if success != "1":
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=success,
                raw_response=raw,
            )

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.verify_url, json={
                    "merchant": self.config.merchant,
                    "trackId": int(track_id),
                })
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        result = data.get("result")
        if result == 100:
            status = PaymentStatus.SUCCESS
        elif result == 201:
            status = PaymentStatus.DUPLICATE
        else:
            status = PaymentStatus.FAILED

        return PaymentResult(
            status=status,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            reference_id=str(data.get("refNumber", "")),
            card_number=data.get("cardNumber"),
            raw_response=data,
            error_code=None if status != PaymentStatus.FAILED else str(result),
        )
