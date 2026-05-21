import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import GatewayConnectionError, GatewayPaymentError
from fastapi_iranian_bank_gateways.gateways.tier3.pay_ir import PayIrConfig, PayIrGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

SEND_URL = "https://pay.ir/pg/send"
VERIFY_URL = "https://pay.ir/pg/verify"


@pytest.fixture
def gateway():
    return PayIrGateway(PayIrConfig(api="test"))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-PIR-001",
        amount=45000,
        callback_url="https://shop.com/payments/pay_ir/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post(SEND_URL).mock(
        return_value=httpx.Response(200, json={"status": 1, "token": "PIR-TOKEN"})
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "PIR-TOKEN" in result.url


@respx.mock
@pytest.mark.asyncio
async def test_initiate_failure(gateway, payment_request):
    respx.post(SEND_URL).mock(
        return_value=httpx.Response(200, json={"status": 0, "errorCode": 5, "errorMessage": "err"})
    )
    with pytest.raises(GatewayPaymentError):
        await gateway.initiate(payment_request)


@respx.mock
@pytest.mark.asyncio
async def test_initiate_connection_error(gateway, payment_request):
    respx.post(SEND_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(GatewayConnectionError):
        await gateway.initiate(payment_request)


@respx.mock
@pytest.mark.asyncio
async def test_verify_success(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={
            "status": 1,
            "transId": "TRANS-PIR-001",
            "cardNumber": "5022****1234",
        })
    )
    callback = BankCallbackData(
        gateway_slug="pay_ir",
        raw={"token": "PIR-TOKEN", "factorNumber": "ORDER-PIR-001", "status": "1"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.transaction_id == "TRANS-PIR-001"


@respx.mock
@pytest.mark.asyncio
async def test_verify_cancelled_by_user(gateway):
    callback = BankCallbackData(
        gateway_slug="pay_ir",
        raw={"token": "PIR-TOKEN", "factorNumber": "ORDER-PIR-001", "status": "0"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.CANCELLED


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_verify_call(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"status": 0, "errorCode": 10})
    )
    callback = BankCallbackData(
        gateway_slug="pay_ir",
        raw={"token": "PIR-TOKEN", "factorNumber": "ORDER-PIR-001", "status": "1"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
