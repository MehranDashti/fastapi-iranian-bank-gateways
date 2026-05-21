import datetime
from typing import ClassVar

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import FormInitiateResponse, InitiateResponse, PaymentRequest
from ....utils.form import render_auto_submit_form
from ....utils.soap import get_soap_client
from .config import MellatConfig


class MellatGateway(AbstractGateway):
    """
    Mellat Bank (به‌پرداخت ملت) payment gateway — SOAP via zeep.
    Requires: pip install "fastapi-iranian-bank-gateways[soap]"
    """

    gateway_slug: ClassVar[str] = "mellat"
    config_class: ClassVar[type] = MellatConfig
    callback_method: ClassVar[str] = "POST"

    def __init__(self, config: MellatConfig) -> None:
        super().__init__(config)
        self.config: MellatConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        client = get_soap_client(self.config.wsdl_url)
        now = datetime.datetime.now()

        response = client.service.bpPayRequest(
            terminalId=self.config.terminal_id,
            userName=self.config.username,
            userPassword=self.config.password,
            orderId=request.order_id,
            amount=request.amount,
            localDate=now.strftime("%Y%m%d"),
            localTime=now.strftime("%H%M%S"),
            additionalData=request.description or "",
            callBackUrl=request.callback_url,
            payerId=0,
            mobileNo=request.mobile or "",
        )

        parts = str(response).split(",")
        res_code = parts[0]
        if res_code != "0":
            raise GatewayPaymentError(
                f"Mellat token request failed with code {res_code}",
                gateway=self.gateway_slug,
                code=res_code,
            )

        ref_id = parts[1]
        html = render_auto_submit_form(
            action=self.config.gateway_url,
            fields={"RefId": ref_id, "MobileNo": request.mobile or ""},
        )
        return FormInitiateResponse(html=html)

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        res_code = str(raw.get("ResCode", "-1"))
        order_id = str(raw.get("SaleOrderId", raw.get("_order_id", "")))

        if res_code not in ("0", "43"):
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=res_code,
                raw_response=raw,
            )

        client = get_soap_client(self.config.wsdl_url)
        verify_response = client.service.bpVerifyRequest(
            terminalId=self.config.terminal_id,
            userName=self.config.username,
            userPassword=self.config.password,
            orderId=raw.get("SaleOrderId", ""),
            saleOrderId=raw.get("SaleOrderId", ""),
            saleReferenceId=raw.get("SaleReferenceId", ""),
        )

        verified_code = str(verify_response)
        if verified_code == "0":
            status = PaymentStatus.SUCCESS
        elif verified_code == "43":
            status = PaymentStatus.DUPLICATE
        else:
            status = PaymentStatus.FAILED

        return PaymentResult(
            status=status,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            reference_id=str(raw.get("SaleReferenceId", "")),
            error_code=None if status != PaymentStatus.FAILED else verified_code,
            raw_response=raw,
        )
