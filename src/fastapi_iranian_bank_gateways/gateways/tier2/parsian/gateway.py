from typing import ClassVar

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from ....utils.soap import get_soap_client
from .config import ParsianConfig


class ParsianGateway(AbstractGateway):
    """
    Parsian Bank (پارسیان) — SOAP via zeep, redirect, POST callback.
    Requires: pip install "fastapi-iranian-bank-gateways[soap]"
    """

    gateway_slug: ClassVar[str] = "parsian"
    config_class: ClassVar[type] = ParsianConfig
    callback_method: ClassVar[str] = "POST"

    def __init__(self, config: ParsianConfig) -> None:
        super().__init__(config)
        self.config: ParsianConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        client = get_soap_client(self.config.token_wsdl)
        response = client.service.SalePaymentRequest(
            requestData={
                "LoginAccount": self.config.login_account,
                "Amount": request.amount,
                "OrderId": int(request.order_id) if request.order_id.isdigit() else 0,
                "CallBackUrl": request.callback_url,
                "AdditionalData": request.description or "",
                "Originator": request.mobile or "",
            }
        )

        status = response.get("Status", -1)
        token = response.get("Token", -1)

        if status == 0 and token != -1:
            return RedirectInitiateResponse(url=f"{self.config.gateway_url}{token}")

        raise GatewayPaymentError(
            f"Parsian token request failed: status={status}",
            gateway=self.gateway_slug,
            code=str(status),
            raw=dict(response),
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        token = str(raw.get("Token", raw.get("token", "")))
        status = str(raw.get("status", raw.get("Status", "-1")))
        order_id = str(raw.get("OrderId", raw.get("_order_id", "")))
        rrn = str(raw.get("RRN", ""))

        if status not in ("0",):
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=status,
                raw_response=raw,
            )

        client = get_soap_client(self.config.confirm_wsdl)
        response = client.service.ConfirmPayment(
            requestData={
                "LoginAccount": self.config.login_account,
                "Token": int(token),
            }
        )

        confirm_status = response.get("Status", -1)
        if confirm_status == 0:
            return PaymentResult(
                status=PaymentStatus.SUCCESS,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                reference_id=rrn,
                raw_response={**raw, **dict(response)},
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            error_code=str(confirm_status),
            raw_response={**raw, **dict(response)},
        )
