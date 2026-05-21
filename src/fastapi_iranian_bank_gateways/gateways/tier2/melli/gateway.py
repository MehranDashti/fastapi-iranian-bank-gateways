from typing import ClassVar

import httpx

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayConnectionError, GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from .config import MelliConfig


class MelliGateway(AbstractGateway):
    """Bank Melli / Behpardakht (به‌پرداخت ملی) — REST, redirect, POST callback."""

    gateway_slug: ClassVar[str] = "melli"
    config_class: ClassVar[type] = MelliConfig
    callback_method: ClassVar[str] = "POST"

    def __init__(self, config: MelliConfig) -> None:
        super().__init__(config)
        self.config: MelliConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        payload = {
            "TerminalId": self.config.terminal_id,
            "MerchantId": self.config.merchant_id,
            "Amount": request.amount,
            "OrderId": request.order_id,
            "LocalDateTime": "",
            "ReturnUrl": request.callback_url,
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.token_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        if data.get("ResCode") == "0":
            token = data["Token"]
            return RedirectInitiateResponse(
                url=f"{self.config.gateway_url}?Token={token}"
            )

        raise GatewayPaymentError(
            f"Melli token request failed: {data}",
            gateway=self.gateway_slug,
            code=str(data.get("ResCode", "")),
            raw=data,
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        res_code = str(raw.get("ResCode", "-1"))
        order_id = str(raw.get("OrderId", raw.get("_order_id", "")))
        sale_ref_num = str(raw.get("SaleReferenceId", ""))

        if res_code != "0":
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=res_code,
                raw_response=raw,
            )

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.verify_url, json={
                    "TerminalId": self.config.terminal_id,
                    "MerchantId": self.config.merchant_id,
                    "OrderId": order_id,
                    "SaleOrderId": order_id,
                    "SaleReferenceId": sale_ref_num,
                })
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        verify_code = str(data.get("ResCode", "-1"))
        return PaymentResult(
            status=PaymentStatus.SUCCESS if verify_code == "0" else PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            reference_id=sale_ref_num,
            raw_response={**raw, **data},
            error_code=None if verify_code == "0" else verify_code,
        )
