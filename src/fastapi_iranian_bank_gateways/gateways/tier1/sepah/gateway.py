from typing import ClassVar

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from ....utils.soap import get_soap_client
from .config import SepahConfig


class SepahGateway(AbstractGateway):
    """
    Sepah Bank (سپه) — SOAP via zeep, server-side redirect, POST callback.
    Requires: pip install "fastapi-iranian-bank-gateways[soap]"
    """

    gateway_slug: ClassVar[str] = "sepah"
    config_class: ClassVar[type] = SepahConfig
    callback_method: ClassVar[str] = "POST"

    def __init__(self, config: SepahConfig) -> None:
        super().__init__(config)
        self.config: SepahConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        client = get_soap_client(self.config.wsdl_url)
        response = client.service.SalePaymentRequest(
            requestData={
                "LoginAccount": self.config.login_account,
                "Amount": request.amount,
                "OrderId": str(request.order_id),
                "CallBackUrl": request.callback_url,
            }
        )

        if response.get("Status") == 0:
            token = response["Token"]
            return RedirectInitiateResponse(
                url=self.config.gateway_redirect_url + str(token)
            )

        raise GatewayPaymentError(
            f"Sepah token request failed: status={response.get('Status')}",
            gateway=self.gateway_slug,
            code=str(response.get("Status", "")),
            raw=dict(response),
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        status = str(raw.get("status", raw.get("Status", "-1")))
        order_id = str(raw.get("OrderId", raw.get("_order_id", "")))
        token = str(raw.get("Token", ""))

        if status != "1":
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=status,
                raw_response=raw,
            )

        client = get_soap_client(self.config.wsdl_url)
        response = client.service.ConfirmPayment(
            requestData={
                "LoginAccount": self.config.login_account,
                "Token": token,
            }
        )

        confirm_status = str(response.get("Status", "-1"))
        if confirm_status == "0":
            return PaymentResult(
                status=PaymentStatus.SUCCESS,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                reference_id=str(response.get("RRN", "")),
                card_number=str(response.get("CardNumberMasked", "")),
                raw_response=dict(response),
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            error_code=confirm_status,
            raw_response=dict(response),
        )
