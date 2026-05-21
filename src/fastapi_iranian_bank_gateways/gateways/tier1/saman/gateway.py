from typing import ClassVar

import httpx

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayAuthError, GatewayConnectionError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import FormInitiateResponse, InitiateResponse, PaymentRequest
from ....utils.form import render_auto_submit_form
from .config import SamanConfig


class SamanGateway(AbstractGateway):
    """Saman Bank (سامان کیش) — REST token, form-POST, GET callback."""

    gateway_slug: ClassVar[str] = "saman"
    config_class: ClassVar[type] = SamanConfig
    callback_method: ClassVar[str] = "GET"

    def __init__(self, config: SamanConfig) -> None:
        super().__init__(config)
        self.config: SamanConfig = config

    async def _get_token(self, request: PaymentRequest) -> str:
        payload = {
            "action": "token",
            "TerminalId": self.config.terminal_id,
            "Amount": request.amount,
            "ResNum": request.order_id,
            "redirectUrl": request.callback_url,
            "cellNumber": request.mobile or "",
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.token_url, data=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        if data.get("status") == 1:
            return str(data["token"])
        raise GatewayAuthError(
            f"Saman token request failed: {data}",
            gateway=self.gateway_slug,
        )

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        token = await self._get_token(request)
        html = render_auto_submit_form(
            action=self.config.gateway_url,
            fields={"Token": token, "GetMethod": "true"},
        )
        return FormInitiateResponse(html=html)

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        state = str(raw.get("State", ""))
        order_id = str(raw.get("ResNum", raw.get("_order_id", "")))
        ref_num = str(raw.get("RefNum", ""))

        if state.upper() != "OK":
            return PaymentResult(
                status=PaymentStatus.FAILED if state else PaymentStatus.CANCELLED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=state,
                raw_response=raw,
            )

        payload = {
            "RefNum": ref_num,
            "TerminalNumber": self.config.terminal_id,
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.verify_url, data=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        success = data.get("Success", False)
        result_code = str(data.get("ResultCode", ""))

        return PaymentResult(
            status=PaymentStatus.SUCCESS if success else PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            reference_id=ref_num,
            card_number=str(raw.get("SecurePan", "")),
            raw_response={**raw, **data},
            error_code=None if success else result_code,
        )
