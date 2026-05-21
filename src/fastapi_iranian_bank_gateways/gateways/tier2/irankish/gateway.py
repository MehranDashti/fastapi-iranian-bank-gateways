from typing import ClassVar

import httpx

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayConnectionError, GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from .config import IrankishConfig


class IrankishGateway(AbstractGateway):
    """Irankish (ایران کیش) — REST, redirect, POST callback."""

    gateway_slug: ClassVar[str] = "irankish"
    config_class: ClassVar[type] = IrankishConfig
    callback_method: ClassVar[str] = "POST"

    def __init__(self, config: IrankishConfig) -> None:
        super().__init__(config)
        self.config: IrankishConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        payload = {
            "terminalId": self.config.terminal_id,
            "acceptorId": self.config.acceptor_id,
            "passPhrase": self.config.pass_phrase,
            "amount": request.amount,
            "revertURL": request.callback_url,
            "specialPaymentId": request.order_id,
            "description": request.description or "",
            "paymentId": request.order_id,
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(
                    self.config.token_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        if data.get("responseCode") == "00" and data.get("token"):
            token = data["token"]
            return RedirectInitiateResponse(
                url=f"{self.config.gateway_url}?token={token}"
            )

        raise GatewayPaymentError(
            f"Irankish token request failed: {data}",
            gateway=self.gateway_slug,
            code=str(data.get("responseCode", "")),
            raw=data,
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        result_code = str(raw.get("resultCode", raw.get("responseCode", "-1")))
        order_id = str(raw.get("paymentId", raw.get("_order_id", "")))
        token = str(raw.get("token", ""))
        rrn = str(raw.get("retrievalReferenceNumber", ""))

        if result_code not in ("00", "0"):
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=result_code,
                raw_response=raw,
            )

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(
                    self.config.verify_url,
                    json={
                        "terminalId": self.config.terminal_id,
                        "acceptorId": self.config.acceptor_id,
                        "passPhrase": self.config.pass_phrase,
                        "token": token,
                        "referenceNumber": rrn,
                        "paymentId": order_id,
                    },
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        verify_code = str(data.get("responseCode", "-1"))
        return PaymentResult(
            status=PaymentStatus.SUCCESS if verify_code == "00" else PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            reference_id=rrn,
            card_number=data.get("maskedCardNumber"),
            raw_response={**raw, **data},
            error_code=None if verify_code == "00" else verify_code,
        )
