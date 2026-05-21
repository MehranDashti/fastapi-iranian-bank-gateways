import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.exceptions import GatewayConnectionError, GatewayPaymentError
from fastapi_iranian_bank_gateways.gateways.tier3.zibal import ZibalConfig, ZibalGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

REQUEST_URL = "https://gateway.zibal.ir/v1/request"
VERIFY_URL = "https://gateway.zibal.ir/v1/verify"


@pytest.fixture
def gateway():
    return ZibalGateway(ZibalConfig(merchant="zibal"))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-ZIB-001",
        amount=80000,
        callback_url="https://shop.com/payments/zibal/verify",
    )


@respx.mock
@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    respx.post(REQUEST_URL).mock(
        return_value=httpx.Response(200, json={"result": 100, "trackId": 123456})
    )
    result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "123456" in result.url


@respx.mock
@pytest.mark.asyncio
async def test_initiate_failure(gateway, payment_request):
    respx.post(REQUEST_URL).mock(
        return_value=httpx.Response(200, json={"result": 102, "message": "merchant not active"})
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
        return_value=httpx.Response(200, json={
            "result": 100,
            "refNumber": "REF-ZIB-001",
            "cardNumber": "6037****1234",
        })
    )
    callback = BankCallbackData(
        gateway_slug="zibal",
        raw={"trackId": "123456", "orderId": "ORDER-ZIB-001", "success": "1"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "REF-ZIB-001"


@respx.mock
@pytest.mark.asyncio
async def test_verify_duplicate(gateway):
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"result": 201, "refNumber": "REF-ZIB-001"})
    )
    callback = BankCallbackData(
        gateway_slug="zibal",
        raw={"trackId": "123456", "orderId": "ORDER-ZIB-001", "success": "1"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.DUPLICATE


@respx.mock
@pytest.mark.asyncio
async def test_verify_failed_callback_success(gateway):
    callback = BankCallbackData(
        gateway_slug="zibal",
        raw={"trackId": "123456", "orderId": "ORDER-ZIB-001", "success": "0"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
