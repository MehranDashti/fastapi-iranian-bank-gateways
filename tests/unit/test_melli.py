import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import GatewayConnectionError, GatewayPaymentError
from fastapi_iranian_bank_gateways.gateways.tier2.melli import MelliConfig, MelliGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

TOKEN_URL = "https://bpms.bpi.ir/pgwchannel/services/rest/PaymentTokenRequest"
VERIFY_URL = "https://bpms.bpi.ir/pgwchannel/services/rest/VerifyPayment"


@pytest.fixture
def gateway():
    return MelliGateway(MelliConfig(terminal_id="T001", merchant_id="M001", sandbox=True))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-MLI-001",
        amount=120000,
        callback_url="https://shop.com/payments/melli/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"ResCode": "0", "Token": "MELLI-TOKEN"})
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "MELLI-TOKEN" in result.url


@respx.mock
@pytest.mark.asyncio
async def test_initiate_failure(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"ResCode": "35", "Description": "Invalid"})
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
        return_value=httpx.Response(200, json={"ResCode": "0"})
    )
    callback = BankCallbackData(
        gateway_slug="melli",
        raw={
            "ResCode": "0",
            "OrderId": "ORDER-MLI-001",
            "SaleReferenceId": "REF-MLI-001",
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "REF-MLI-001"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_callback_rescode(gateway):
    callback = BankCallbackData(
        gateway_slug="melli",
        raw={"ResCode": "17", "OrderId": "ORDER-MLI-001"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "17"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_verify_call(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"ResCode": "43"})
    )
    callback = BankCallbackData(
        gateway_slug="melli",
        raw={"ResCode": "0", "OrderId": "ORDER-MLI-001", "SaleReferenceId": "REF-001"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
