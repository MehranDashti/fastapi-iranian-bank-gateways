from typing import ClassVar

from ....adapters import HttpTransportAdapter
from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from .config import ZarinpalConfig


class ZarinpalGateway(AbstractGateway):
    """Zarinpal (زرین‌پال) — REST/JSON, redirect, GET callback."""

    gateway_slug: ClassVar[str] = "zarinpal"
    config_class: ClassVar[type] = ZarinpalConfig
    callback_method: ClassVar[str] = "GET"

    def __init__(
        self,
        config: ZarinpalConfig,
        transport: HttpTransportAdapter | None = None,
    ) -> None:
        super().__init__(config, transport)
        self.config: ZarinpalConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        payload = {
            "merchant_id": self.config.merchant_id,
            "amount": request.amount,
            "callback_url": request.callback_url,
            "description": request.description or f"Order {request.order_id}",
            "metadata": {
                "mobile": request.mobile,
                "email": request.email,
                "order_id": request.order_id,
            },
        }
        data = await self.transport.post(
            self.config.payment_url,
            payload,
            None,
            self.config.timeout,
        )

        data_field = data.get("data")
        if not isinstance(data_field, dict):
            data_field = {}
        code = data_field.get("code")
        if code == 100:
            authority = data_field["authority"]
            return RedirectInitiateResponse(
                url=f"{self.config.start_pay_url}{authority}"
            )

        err = data.get("errors") or {}
        if not isinstance(err, dict):
            err = {}
        raise GatewayPaymentError(
            f"Zarinpal initiation failed: {err}",
            gateway=self.gateway_slug,
            code=str(err.get("code", "")),
            raw=data,
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        order_id = str(raw.get("_order_id", ""))

        if raw.get("Status") != "OK":
            return PaymentResult(
                status=PaymentStatus.CANCELLED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                raw_response=raw,
            )

        amount = raw.get("_amount")
        if not amount:
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_message="Could not determine order amount for verification",
                raw_response=raw,
            )

        data = await self.transport.post(
            self.config.verify_url,
            {
                "merchant_id": self.config.merchant_id,
                "authority": raw.get("Authority"),
                "amount": int(amount),
            },
            None,
            self.config.timeout,
        )

        code = data.get("data", {}).get("code")
        if code == 100:
            status = PaymentStatus.SUCCESS
        elif code == 101:
            status = PaymentStatus.DUPLICATE
        else:
            status = PaymentStatus.FAILED

        return PaymentResult(
            status=status,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            reference_id=str(data.get("data", {}).get("ref_id", "")),
            card_number=data.get("data", {}).get("card_pan"),
            amount=int(amount),
            raw_response=data,
            error_code=None if status != PaymentStatus.FAILED else str(code),
        )
