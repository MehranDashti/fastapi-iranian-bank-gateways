import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import (
    GatewayAuthError,
    GatewayConnectionError,
    GatewayPaymentError,
)
from fastapi_iranian_bank_gateways.gateways.tier2.eghtesad_novin import (
    EghtesadNovinConfig,
    EghtesadNovinGateway,
)
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

TOKEN_URL = "https://ipg.en-bank.ir/igprest/api/v1/merchants/token"
PAYMENT_URL = "https://ipg.en-bank.ir/igprest/api/v1/merchants/payment"
VERIFY_URL = "https://ipg.en-bank.ir/igprest/api/v1/merchants/verify"


@pytest.fixture
def gateway():
    return EghtesadNovinGateway(EghtesadNovinConfig(
        username="enuser",
        password="enpass",
        merchant_id="EN-MERCH-001",
    ))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-EN-001",
        amount=500000,
        callback_url="https://shop.com/payments/eghtesad_novin/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"Token": "AUTH-TOKEN"})
    )
    respx.post(PAYMENT_URL).mock(
        return_value=httpx.Response(200, json={"Token": "PAY-TOKEN"})
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "PAY-TOKEN" in result.url


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
        return_value=httpx.Response(200, json={"Token": "AUTH-TOKEN"})
    )
    respx.post(PAYMENT_URL).mock(
        return_value=httpx.Response(200, json={"error": "payment failed"})
    )
    with pytest.raises(GatewayPaymentError):
        await gateway.initiate(payment_request)


@respx.mock
@pytest.mark.asyncio
async def test_verify_success(gateway):
    # Two auth token calls: one in verify() for the verify step
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"Token": "AUTH-TOKEN"})
    )
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={
            "Status": "0",
            "RRN": "RRN-EN-001",
            "MaskedCardNumber": "6274****1234",
        })
    )
    callback = BankCallbackData(
        gateway_slug="eghtesad_novin",
        raw={"Token": "PAY-TOKEN", "OrderId": "ORDER-EN-001", "Status": "0"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "RRN-EN-001"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_callback_status(gateway):
    callback = BankCallbackData(
        gateway_slug="eghtesad_novin",
        raw={"Token": "PAY-TOKEN", "OrderId": "ORDER-EN-001", "Status": "1"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "1"


@respx.mock
@pytest.mark.asyncio
async def test_verify_connection_error(gateway):
    respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectError("refused"))
    callback = BankCallbackData(
        gateway_slug="eghtesad_novin",
        raw={"Token": "PAY-TOKEN", "OrderId": "ORDER-EN-001", "Status": "0"},
    )
    with pytest.raises(GatewayConnectionError):
        await gateway.verify(callback)
