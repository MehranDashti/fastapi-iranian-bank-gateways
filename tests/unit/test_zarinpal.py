import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import GatewayPaymentError
from fastapi_iranian_bank_gateways.gateways import ZarinpalGateway
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest


@pytest.fixture
def gateway():
    config = ZarinpalConfig(merchant_id="test-merchant-00000000000000000000", sandbox=True)
    return ZarinpalGateway(config)


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-001",
        amount=100000,
        callback_url="https://shop.com/payments/zarinpal/verify",
        mobile="09123456789",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post("https://sandbox.zarinpal.com/pg/v4/payment/request.json").mock(
        return_value=httpx.Response(200, json={
            "data": {"code": 100, "authority": "A00000000000000000000000000123456789"},
            "errors": [],
        })
    )

    result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "A00000000000000000000000000123456789" in result.url


@respx.mock
@pytest.mark.asyncio
async def test_initiate_failure(gateway, payment_request):
    respx.post("https://sandbox.zarinpal.com/pg/v4/payment/request.json").mock(
        return_value=httpx.Response(200, json={
            "data": [],
            "errors": {"code": -9, "message": "Invalid merchant_id"},
        })
    )

    with pytest.raises(GatewayPaymentError):
        await gateway.initiate(payment_request)


@respx.mock
@pytest.mark.asyncio
async def test_verify_success(gateway):
    respx.post("https://sandbox.zarinpal.com/pg/v4/payment/verify.json").mock(
        return_value=httpx.Response(200, json={
            "data": {
                "code": 100,
                "ref_id": 123456,
                "card_pan": "6037-****-****-1234",
            },
            "errors": [],
        })
    )

    callback = BankCallbackData(
        gateway_slug="zarinpal",
        raw={
            "Authority": "A00000000000000000000000000123456789",
            "Status": "OK",
            "_amount": 100000,
            "_order_id": "ORDER-001",
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "123456"
    assert result.card_number == "6037-****-****-1234"


@respx.mock
@pytest.mark.asyncio
async def test_verify_cancelled(gateway):
    callback = BankCallbackData(
        gateway_slug="zarinpal",
        raw={
            "Authority": "A00000000000000000000000000123456789",
            "Status": "NOK",
            "_order_id": "ORDER-001",
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.CANCELLED


@respx.mock
@pytest.mark.asyncio
async def test_verify_duplicate(gateway):
    respx.post("https://sandbox.zarinpal.com/pg/v4/payment/verify.json").mock(
        return_value=httpx.Response(200, json={
            "data": {"code": 101, "ref_id": 123456},
            "errors": [],
        })
    )

    callback = BankCallbackData(
        gateway_slug="zarinpal",
        raw={
            "Authority": "A00000000000000000000000000123456789",
            "Status": "OK",
            "_amount": 100000,
            "_order_id": "ORDER-001",
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.DUPLICATE
