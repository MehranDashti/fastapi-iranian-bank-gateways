import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import GatewayConnectionError, GatewayPaymentError
from fastapi_iranian_bank_gateways.gateways.tier3.vandar import VandarConfig, VandarGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

SEND_URL = "https://ipg.vandar.io/api/v3/send"
VERIFY_URL = "https://ipg.vandar.io/api/v3/verify"


@pytest.fixture
def gateway():
    return VandarGateway(VandarConfig(api_key="VAN-API-KEY"))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-VAN-001",
        amount=350000,
        callback_url="https://shop.com/payments/vandar/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post(SEND_URL).mock(
        return_value=httpx.Response(200, json={"status": 1, "token": "VAN-TOKEN"})
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "VAN-TOKEN" in result.url


@respx.mock
@pytest.mark.asyncio
async def test_initiate_failure(gateway, payment_request):
    respx.post(SEND_URL).mock(
        return_value=httpx.Response(200, json={"status": 0, "errors": ["invalid key"]})
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
            "transId": "TRANS-VAN-001",
            "cardNumber": "6037****5678",
        })
    )
    callback = BankCallbackData(
        gateway_slug="vandar",
        raw={
            "token": "VAN-TOKEN",
            "factorNumber": "ORDER-VAN-001",
            "payment_status": "DONE",
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "TRANS-VAN-001"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_not_done(gateway):
    callback = BankCallbackData(
        gateway_slug="vandar",
        raw={
            "token": "VAN-TOKEN",
            "factorNumber": "ORDER-VAN-001",
            "payment_status": "FAILED",
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "FAILED"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_verify_call(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"status": 0, "errors": ["duplicate"]})
    )
    callback = BankCallbackData(
        gateway_slug="vandar",
        raw={
            "token": "VAN-TOKEN",
            "factorNumber": "ORDER-VAN-001",
            "payment_status": "DONE",
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
