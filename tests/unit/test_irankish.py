import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import GatewayConnectionError, GatewayPaymentError
from fastapi_iranian_bank_gateways.gateways.tier2.irankish import IrankishConfig, IrankishGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

TOKEN_URL = "https://ikc.shaparak.ir/TToken/Tokens.ngx"
VERIFY_URL = "https://ikc.shaparak.ir/TVerify/Verify.ngx"


@pytest.fixture
def gateway():
    return IrankishGateway(IrankishConfig(
        terminal_id="T001",
        acceptor_id="A001",
        pass_phrase="PHRASE",
    ))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-IK-001",
        amount=90000,
        callback_url="https://shop.com/payments/irankish/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"responseCode": "00", "token": "IK-TOKEN"})
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "IK-TOKEN" in result.url


@respx.mock
@pytest.mark.asyncio
async def test_initiate_failure(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"responseCode": "03", "description": "Error"})
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
            "responseCode": "00",
            "maskedCardNumber": "6037****1234",
        })
    )
    callback = BankCallbackData(
        gateway_slug="irankish",
        raw={
            "resultCode": "00",
            "paymentId": "ORDER-IK-001",
            "token": "IK-TOKEN",
            "retrievalReferenceNumber": "RRN-IK-001",
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "RRN-IK-001"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_callback_code(gateway):
    callback = BankCallbackData(
        gateway_slug="irankish",
        raw={"resultCode": "05", "paymentId": "ORDER-IK-001"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "05"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_verify_call(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"responseCode": "14"})
    )
    callback = BankCallbackData(
        gateway_slug="irankish",
        raw={
            "resultCode": "00",
            "paymentId": "ORDER-IK-001",
            "token": "IK-TOKEN",
            "retrievalReferenceNumber": "RRN-001",
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
