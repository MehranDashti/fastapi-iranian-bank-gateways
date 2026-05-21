import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import GatewayConnectionError, GatewayPaymentError
from fastapi_iranian_bank_gateways.gateways.tier3.payping import PayPingConfig, PayPingGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

REQUEST_URL = "https://api.payping.ir/v2/pay"
VERIFY_URL = "https://api.payping.ir/v2/pay/verify"


@pytest.fixture
def gateway():
    return PayPingGateway(PayPingConfig(access_token="PP-ACCESS-TOKEN"))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-PP-001",
        amount=100000,  # 100000 IRR = 10000 Tomans
        callback_url="https://shop.com/payments/payping/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post(REQUEST_URL).mock(
        return_value=httpx.Response(200, json={"code": "PP-CODE-001"})
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "PP-CODE-001" in result.url


@respx.mock
@pytest.mark.asyncio
async def test_initiate_toman_conversion(gateway, payment_request):
    """PayPing receives Tomans (IRR // 10)."""
    captured_payload = {}

    def capture(request):
        import json
        captured_payload.update(json.loads(request.content))
        return httpx.Response(200, json={"code": "PP-CODE-001"})

    respx.post(REQUEST_URL).mock(side_effect=capture)
    await gateway.initiate(payment_request)
    assert captured_payload["amount"] == 10000  # 100000 // 10


@respx.mock
@pytest.mark.asyncio
async def test_initiate_failure(gateway, payment_request):
    respx.post(REQUEST_URL).mock(
        return_value=httpx.Response(200, json={"description": "invalid token"})
    )
    with pytest.raises(GatewayPaymentError):
        await gateway.initiate(payment_request)


@respx.mock
@pytest.mark.asyncio
async def test_initiate_connection_error(gateway, payment_request):
    respx.post(REQUEST_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(GatewayConnectionError):
        await gateway.initiate(payment_request)


@respx.mock
@pytest.mark.asyncio
async def test_verify_success(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"cardNumber": "6037****1234"})
    )
    callback = BankCallbackData(
        gateway_slug="payping",
        raw={
            "code": "PP-CODE-001",
            "refid": "REF-PP-001",
            "clientrefid": "ORDER-PP-001",
            "_amount": 100000,
        },
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.card_number == "6037****1234"
    assert result.reference_id == "REF-PP-001"


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_no_card(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"error": "failed"})
    )
    callback = BankCallbackData(
        gateway_slug="payping",
        raw={"code": "PP-CODE-001", "refid": "REF-PP-001", "clientrefid": "ORDER-PP-001"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
