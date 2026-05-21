import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.gateways import IDPayGateway
from fastapi_iranian_bank_gateways.gateways.tier3.idpay import IDPayConfig
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest


@pytest.fixture
def gateway():
    return IDPayGateway(IDPayConfig(api_key="test-api-key", sandbox=True))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-002",
        amount=50000,
        callback_url="https://shop.com/payments/idpay/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post("https://api.idpay.ir/v1.1/payment").mock(
        return_value=httpx.Response(201, json={
            "id": "payment-id-123",
            "link": "https://idpay.ir/p/ws/payment-id-123",
        })
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "idpay.ir" in result.url


@respx.mock
@pytest.mark.asyncio
async def test_verify_success(gateway):
    respx.post("https://api.idpay.ir/v1.1/payment/verify").mock(
        return_value=httpx.Response(200, json={
            "status": 100,
            "track_id": "TRK-456",
            "payment": {"card_no": "6037****1234"},
        })
    )
    callback = BankCallbackData(
        gateway_slug="idpay",
        raw={
            "id": "payment-id-123", "order_id": "ORDER-002",
            "status": 2, "_order_id": "ORDER-002",
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "TRK-456"


@respx.mock
@pytest.mark.asyncio
async def test_verify_already_verified(gateway):
    respx.post("https://api.idpay.ir/v1.1/payment/verify").mock(
        return_value=httpx.Response(200, json={"status": 200, "track_id": "TRK-456", "payment": {}})
    )
    callback = BankCallbackData(
        gateway_slug="idpay",
        raw={"id": "pid", "order_id": "ORDER-002", "status": 2, "_order_id": "ORDER-002"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.DUPLICATE
