import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import GatewayAuthError, GatewayConnectionError
from fastapi_iranian_bank_gateways.gateways.tier1.saderat import SaderatConfig, SaderatGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

TOKEN_URL = "https://mabna.shaparak.ir:8080/V1/PeymentApi/GetToken"
VERIFY_URL = "https://mabna.shaparak.ir:8080/V1/PeymentApi/Advice"


@pytest.fixture
def gateway():
    return SaderatGateway(SaderatConfig(terminal_id="12345678"))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-SAD-001",
        amount=150000,
        callback_url="https://shop.com/payments/saderat/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"Status": 0, "Accesstoken": "TOKEN-ABC"})
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "form"
    assert "TOKEN-ABC" in result.html


@respx.mock
@pytest.mark.asyncio
async def test_initiate_failure_bad_credentials(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"Status": 1, "Message": "Invalid terminal"})
    )
    with pytest.raises(GatewayAuthError):
        await gateway.initiate(payment_request)


@respx.mock
@pytest.mark.asyncio
async def test_initiate_connection_error(gateway, payment_request):
    respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectError("Connection refused"))
    with pytest.raises(GatewayConnectionError):
        await gateway.initiate(payment_request)


@respx.mock
@pytest.mark.asyncio
async def test_verify_success(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"Status": "OK"})
    )
    callback = BankCallbackData(
        gateway_slug="saderat",
        raw={
            "respcode": "0",
            "digitalreceipt": "REC-001",
            "invoiceid": "ORDER-SAD-001",
            "rrn": "12345678",
            "cardnumber": "6037****1234",
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "12345678"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_bad_respcode(gateway):
    callback = BankCallbackData(
        gateway_slug="saderat",
        raw={"respcode": "99", "invoiceid": "ORDER-SAD-001"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "99"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_verify_call(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"Status": "FAIL"})
    )
    callback = BankCallbackData(
        gateway_slug="saderat",
        raw={"respcode": "0", "digitalreceipt": "REC-001", "invoiceid": "ORDER-SAD-001"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
