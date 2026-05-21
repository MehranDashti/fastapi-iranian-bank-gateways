import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import GatewayConnectionError, GatewayPaymentError
from fastapi_iranian_bank_gateways.gateways.tier3.nextpay import NextPayConfig, NextPayGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

TOKEN_URL = "https://nextpay.org/nx/gateway/token"
VERIFY_URL = "https://nextpay.org/nx/gateway/verify"


@pytest.fixture
def gateway():
    return NextPayGateway(NextPayConfig(api_key="test-key-12345"))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-NXT-001",
        amount=60000,
        callback_url="https://shop.com/payments/nextpay/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"code": -1, "trans_id": "NXT-TRANS-001"})
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "NXT-TRANS-001" in result.url


@respx.mock
@pytest.mark.asyncio
async def test_initiate_failure(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"code": -2, "description": "Invalid api key"})
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
            "code": -90,
            "Shaparak_Ref_Id": "SHAP-001",
            "card_holder": "6037****1234",
        })
    )
    callback = BankCallbackData(
        gateway_slug="nextpay",
        raw={
            "trans_id": "NXT-TRANS-001",
            "order_id": "ORDER-NXT-001",
            "_amount": 60000,
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "SHAP-001"


@respx.mock
@pytest.mark.asyncio
async def test_verify_duplicate(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"code": 0, "Shaparak_Ref_Id": "SHAP-001"})
    )
    callback = BankCallbackData(
        gateway_slug="nextpay",
        raw={"trans_id": "NXT-TRANS-001", "order_id": "ORDER-NXT-001", "_amount": 60000},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.DUPLICATE


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"code": -1, "description": "failed"})
    )
    callback = BankCallbackData(
        gateway_slug="nextpay",
        raw={"trans_id": "NXT-TRANS-001", "order_id": "ORDER-NXT-001", "_amount": 60000},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "-1"
