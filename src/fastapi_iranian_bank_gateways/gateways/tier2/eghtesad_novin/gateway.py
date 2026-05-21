from typing import ClassVar

import httpx

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayAuthError, GatewayConnectionError, GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from .config import EghtesadNovinConfig


class EghtesadNovinGateway(AbstractGateway):
    """Eghtesad Novin Bank (اقتصاد نوین) — REST, redirect, POST callback."""

    gateway_slug: ClassVar[str] = "eghtesad_novin"
    config_class: ClassVar[type] = EghtesadNovinConfig
    callback_method: ClassVar[str] = "POST"

    def __init__(self, config: EghtesadNovinConfig) -> None:
        super().__init__(config)
        self.config: EghtesadNovinConfig = config

    async def _get_token(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.token_url, json={
                    "UserName": self.config.username,
                    "Password": self.config.password,
                    "MerchantId": self.config.merchant_id,
                })
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        token = data.get("Token")
        if token:
            return str(token)
        raise GatewayAuthError(
            f"Eghtesad Novin auth failed: {data}",
            gateway=self.gateway_slug,
        )

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        token = await self._get_token()
        payload = {
            "Token": token,
            "Amount": request.amount,
            "MerchantId": self.config.merchant_id,
            "OrderId": request.order_id,
            "ReturnURL": request.callback_url,
            "MobileNo": request.mobile or "",
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(
                    f"{self.config.gateway_url}/igprest/api/v1/merchants/payment",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        pay_token = data.get("Token")
        if pay_token:
            return RedirectInitiateResponse(
                url=f"{self.config.gateway_url}/igprest/api/v1/merchants/startpay?token={pay_token}"
            )

        raise GatewayPaymentError(
            f"Eghtesad Novin payment initiation failed: {data}",
            gateway=self.gateway_slug,
            raw=data,
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        pay_token = str(raw.get("Token", ""))
        order_id = str(raw.get("OrderId", raw.get("_order_id", "")))
        status_code = str(raw.get("Status", "-1"))

        if status_code != "0":
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=status_code,
                raw_response=raw,
            )

        auth_token = await self._get_token()
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.verify_url, json={
                    "Token": auth_token,
                    "PayToken": pay_token,
                    "MerchantId": self.config.merchant_id,
                })
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        verify_status = str(data.get("Status", "-1"))
        if verify_status == "0":
            return PaymentResult(
                status=PaymentStatus.SUCCESS,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                reference_id=str(data.get("RRN", "")),
                card_number=data.get("MaskedCardNumber"),
                raw_response={**raw, **data},
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            error_code=verify_status,
            raw_response={**raw, **data},
        )
