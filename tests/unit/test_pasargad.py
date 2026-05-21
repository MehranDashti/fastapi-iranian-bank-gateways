import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import (
    GatewayAuthError,
    GatewayConnectionError,
    GatewayPaymentError,
)
from fastapi_iranian_bank_gateways.gateways.tier1.pasargad import PasargadConfig, PasargadGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

TOKEN_URL = "https://pep.shaparak.ir/Api/v1/Payment/GetToken"
PURCHASE_URL = "https://pep.shaparak.ir/Api/v1/Payment/GetUrlAndToken"
CHECK_URL = "https://pep.shaparak.ir/Api/v1/Payment/CheckTransactionResult"
VERIFY_URL = "https://pep.shaparak.ir/Api/v1/Payment/VerifyPayment"


@pytest.fixture
def gateway():
    return PasargadGateway(PasargadConfig(
        username="user",
        password="pass",
        terminal_number="12345",
        merchant_code="MERCH001",
    ))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-PAS-001",
        amount=300000,
        callback_url="https://shop.com/payments/pasargad/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"token": "BEARER-TOKEN"})
    )
    respx.post(PURCHASE_URL).mock(
        return_value=httpx.Response(200, json={
            "resultCode": 0,
            "data": {"url": "https://pep.shaparak.ir/payment/12345"},
        })
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "pep.shaparak.ir" in result.url


@respx.mock
@pytest.mark.asyncio
async def test_initiate_auth_failure(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"error": "invalid credentials"})
    )
    with pytest.raises(GatewayAuthError):
        await gateway.initiate(payment_request)


@respx.mock
@pytest.mark.asyncio
async def test_initiate_payment_failure(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"token": "BEARER-TOKEN"})
    )
    respx.post(PURCHASE_URL).mock(
        return_value=httpx.Response(200, json={"resultCode": 1, "message": "Failed"})
    )
    with pytest.raises(GatewayPaymentError):
        await gateway.initiate(payment_request)


@respx.mock
@pytest.mark.asyncio
async def test_verify_success(gateway):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"token": "BEARER-TOKEN"})
    )
    respx.post(CHECK_URL).mock(
        return_value=httpx.Response(200, json={"resultCode": 0})
    )
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"resultCode": 0, "traceNumber": "TRC-001"})
    )
    callback = BankCallbackData(
        gateway_slug="pasargad",
        raw={"iN": "ORDER-PAS-001", "tref": "TRC-001", "iD": "URL-ID"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "TRC-001"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_check(gateway):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"token": "BEARER-TOKEN"})
    )
    respx.post(CHECK_URL).mock(
        return_value=httpx.Response(200, json={"resultCode": 1, "message": "Not found"})
    )
    callback = BankCallbackData(
        gateway_slug="pasargad",
        raw={"iN": "ORDER-PAS-001", "tref": "", "iD": ""},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "1"


@respx.mock
@pytest.mark.asyncio
async def test_verify_connection_error(gateway):
    respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectError("refused"))
    callback = BankCallbackData(
        gateway_slug="pasargad",
        raw={"iN": "ORDER-PAS-001", "tref": "", "iD": ""},
    )
    with pytest.raises(GatewayConnectionError):
        await gateway.verify(callback)
