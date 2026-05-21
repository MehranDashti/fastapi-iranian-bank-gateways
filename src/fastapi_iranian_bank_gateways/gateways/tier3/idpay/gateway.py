from typing import ClassVar

from ....adapters import HttpTransportAdapter
from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from .config import IDPayConfig


class IDPayGateway(AbstractGateway):
    """IDPay (آیدی پی) — REST/JSON, redirect, POST callback."""

    gateway_slug: ClassVar[str] = "idpay"
    config_class: ClassVar[type] = IDPayConfig
    callback_method: ClassVar[str] = "POST"

    def __init__(
        self,
        config: IDPayConfig,
        transport: HttpTransportAdapter | None = None,
    ) -> None:
        super().__init__(config, transport)
        self.config: IDPayConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        payload = {
            "order_id": request.order_id,
            "amount": request.amount,
            "callback": request.callback_url,
            "desc": request.description or f"Order {request.order_id}",
            "phone": request.mobile,
            "mail": request.email,
        }
        data = await self.transport.post(
            self.config.payment_url,
            payload,
            self.config._headers(),
            self.config.timeout,
        )

        if "link" in data:
            return RedirectInitiateResponse(url=data["link"])

        raise GatewayPaymentError(
            f"IDPay initiation failed: {data}",
            gateway=self.gateway_slug,
            code=str(data.get("error_code", "")),
            raw=data,
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        order_id = str(raw.get("order_id", raw.get("_order_id", "")))
        payment_id = str(raw.get("id", ""))
        cb_status = int(raw.get("status", 0))

        # IDPay status 1=not paid, 2=paid, 3=error, 100=verified, 101=already verified
        if cb_status not in (2, 100, 101):
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=str(cb_status),
                raw_response=raw,
            )

        data = await self.transport.post(
            self.config.verify_url,
            {"id": payment_id, "order_id": order_id},
            self.config._headers(),
            self.config.timeout,
        )

        verify_status = int(data.get("status", 0))
        if verify_status == 100:
            status = PaymentStatus.SUCCESS
        elif verify_status == 200:
            status = PaymentStatus.DUPLICATE
        else:
            status = PaymentStatus.FAILED

        return PaymentResult(
            status=status,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            transaction_id=payment_id,
            reference_id=str(data.get("track_id", "")),
            card_number=data.get("payment", {}).get("card_no"),
            raw_response=data,
            error_code=None if status != PaymentStatus.FAILED else str(verify_status),
        )
