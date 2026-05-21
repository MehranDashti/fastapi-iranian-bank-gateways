import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import GatewayAuthError, GatewayConnectionError
from fastapi_iranian_bank_gateways.gateways.tier1.saman import SamanConfig, SamanGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

TOKEN_URL = "https://sep.shaparak.ir/onlinepg/onlinepg"
VERIFY_URL = "https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction"


@pytest.fixture
def gateway():
    return SamanGateway(SamanConfig(terminal_id="10000000", password="pass"))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-SAM-001",
        amount=200000,
        callback_url="https://shop.com/payments/saman/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"status": 1, "token": "SAMAN-TOKEN"})
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "form"
    assert "SAMAN-TOKEN" in result.html


@respx.mock
@pytest.mark.asyncio
async def test_initiate_failure(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"status": -1, "errorDesc": "Invalid terminal"})
    )
    with pytest.raises(GatewayAuthError):
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
        return_value=httpx.Response(200, json={"Success": True, "ResultCode": 0})
    )
    callback = BankCallbackData(
        gateway_slug="saman",
        raw={
            "State": "OK",
            "ResNum": "ORDER-SAM-001",
            "RefNum": "REF-001",
            "SecurePan": "6219****1234",
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "REF-001"


@respx.mock
@pytest.mark.asyncio
async def test_verify_cancelled(gateway):
    callback = BankCallbackData(
        gateway_slug="saman",
        raw={"State": "", "ResNum": "ORDER-SAM-001"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.CANCELLED


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_state(gateway):
    callback = BankCallbackData(
        gateway_slug="saman",
        raw={"State": "CANCEL", "ResNum": "ORDER-SAM-001"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_verify_call(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"Success": False, "ResultCode": 2})
    )
    callback = BankCallbackData(
        gateway_slug="saman",
        raw={"State": "OK", "ResNum": "ORDER-SAM-001", "RefNum": "REF-001"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "2"
