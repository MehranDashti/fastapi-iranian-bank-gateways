from typing import ClassVar

import httpx

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayAuthError, GatewayConnectionError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import FormInitiateResponse, InitiateResponse, PaymentRequest
from ....utils.form import render_auto_submit_form
from .config import SaderatConfig


class SaderatGateway(AbstractGateway):
    """Saderat Bank (پرداخت الکترونیک صادرات ایران) — REST, form-POST, GET callback."""

    gateway_slug: ClassVar[str] = "saderat"
    config_class: ClassVar[type] = SaderatConfig
    callback_method: ClassVar[str] = "GET"

    def __init__(self, config: SaderatConfig) -> None:
        super().__init__(config)
        self.config: SaderatConfig = config

    async def _get_access_token(self, request: PaymentRequest) -> str:
        payload = {
            "Amount": request.amount,
            "callbackURL": request.callback_url,
            "InvoiceID": request.order_id,
            "TerminalID": self.config.terminal_id,
            "Payload": [],
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.token_url, data=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        if data.get("Status") == 0:
            return str(data["Accesstoken"])
        raise GatewayAuthError(
            f"Saderat token request failed: {data}",
            gateway=self.gateway_slug,
        )

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        token = await self._get_access_token(request)
        html = render_auto_submit_form(
            action=self.config.gateway_url,
            fields={
                "TerminalID": self.config.terminal_id,
                "Token": token,
            },
        )
        return FormInitiateResponse(html=html)

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        digital_receipt = raw.get("digitalreceipt", "")
        resp_code = str(raw.get("respcode", "-1"))
        order_id = str(raw.get("invoiceid", raw.get("_order_id", "")))

        if resp_code not in ("0", "00"):
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=resp_code,
                raw_response=raw,
            )

        payload = {
            "digitalreceipt": digital_receipt,
            "Tid": self.config.terminal_id,
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.verify_url, data=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        verify_status = str(data.get("Status", "-1"))
        if verify_status in ("0", "OK"):
            status = PaymentStatus.SUCCESS
        else:
            status = PaymentStatus.FAILED

        return PaymentResult(
            status=status,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            reference_id=str(raw.get("rrn", "")),
            card_number=str(raw.get("cardnumber", "")),
            raw_response={**raw, **data},
            error_code=None if status == PaymentStatus.SUCCESS else verify_status,
        )
