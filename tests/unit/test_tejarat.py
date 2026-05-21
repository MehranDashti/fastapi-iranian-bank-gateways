import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import GatewayConnectionError, GatewayPaymentError
from fastapi_iranian_bank_gateways.gateways.tier2.tejarat import TejaratConfig, TejaratGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

TOKEN_URL = "https://agt.tejaratpay.com/ipg/api/v1/token"
VERIFY_URL = "https://agt.tejaratpay.com/ipg/api/v1/payment"


@pytest.fixture
def gateway():
    return TejaratGateway(TejaratConfig(terminal_id="TEJ-001"))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-TEJ-001",
        amount=75000,
        callback_url="https://shop.com/payments/tejarat/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"token": "TEJ-TOKEN"})
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "TEJ-TOKEN" in result.url


@respx.mock
@pytest.mark.asyncio
async def test_initiate_failure(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"error": "Invalid terminal"})
    )
    with pytest.raises(GatewayPaymentError):
        await gateway.initiate(payment_request)


@respx.mock
@pytest.mark.asyncio
async def test_initiate_connection_error(gateway, payment_request):
    respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(GatewayConnectionError):
        await gateway.initiate(payment_request)


@respx.mock
@pytest.mark.asyncio
async def test_verify_success(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={
            "status": "0",
            "traceNumber": "TRC-TEJ-001",
            "maskedCardNumber": "5022****1234",
        })
    )
    callback = BankCallbackData(
        gateway_slug="tejarat",
        raw={"token": "TEJ-TOKEN", "invoiceNumber": "ORDER-TEJ-001", "status": "0"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "TRC-TEJ-001"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_callback_status(gateway):
    callback = BankCallbackData(
        gateway_slug="tejarat",
        raw={"token": "TEJ-TOKEN", "invoiceNumber": "ORDER-TEJ-001", "status": "-1"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "-1"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_verify_call(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"status": "-99"})
    )
    callback = BankCallbackData(
        gateway_slug="tejarat",
        raw={"token": "TEJ-TOKEN", "invoiceNumber": "ORDER-TEJ-001", "status": "1"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
