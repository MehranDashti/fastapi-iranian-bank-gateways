"""Tests for HttpTransportAdapter, HttpxAdapter, and InMemoryAdapter."""
import httpx
import pytest
import respx

from fastapi_iranian_bank_gateways.adapters import (
    HttpTransportAdapter,
    HttpxAdapter,
    InMemoryAdapter,
)
from fastapi_iranian_bank_gateways.exceptions import GatewayConnectionError
from fastapi_iranian_bank_gateways.gateways import IDPayGateway, ZarinpalGateway
from fastapi_iranian_bank_gateways.gateways.tier3.idpay import IDPayConfig
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

def test_in_memory_adapter_is_transport_adapter():
    adapter = InMemoryAdapter({})
    assert isinstance(adapter, HttpTransportAdapter)


def test_httpx_adapter_is_transport_adapter():
    adapter = HttpxAdapter()
    assert isinstance(adapter, HttpTransportAdapter)


# ---------------------------------------------------------------------------
# InMemoryAdapter unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_in_memory_adapter_post_returns_configured_response():
    adapter = InMemoryAdapter({
        "https://api.example.com/pay": {"status": 1, "token": "TOKEN123"},
    })
    result = await adapter.post("https://api.example.com/pay", {"amount": 1000}, None, 30.0)
    assert result == {"status": 1, "token": "TOKEN123"}


@pytest.mark.asyncio
async def test_in_memory_adapter_get_returns_configured_response():
    adapter = InMemoryAdapter({
        "https://api.example.com/info": {"data": "ok"},
    })
    result = await adapter.get("https://api.example.com/info", None, None, 30.0)
    assert result == {"data": "ok"}


@pytest.mark.asyncio
async def test_in_memory_adapter_records_post_call():
    adapter = InMemoryAdapter({
        "https://api.example.com/pay": {"result": "ok"},
    })
    await adapter.post("https://api.example.com/pay", {"amount": 500}, {"X-Key": "k"}, 30.0)

    assert len(adapter.calls) == 1
    call = adapter.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.example.com/pay"
    assert call["payload"] == {"amount": 500}
    assert call["headers"] == {"X-Key": "k"}


@pytest.mark.asyncio
async def test_in_memory_adapter_records_get_call():
    adapter = InMemoryAdapter({
        "https://api.example.com/status": {"active": True},
    })
    await adapter.get("https://api.example.com/status", {"id": "1"}, None, 30.0)

    assert adapter.calls[0]["method"] == "GET"
    assert adapter.calls[0]["params"] == {"id": "1"}


@pytest.mark.asyncio
async def test_in_memory_adapter_raises_configured_exception():
    adapter = InMemoryAdapter({
        "https://api.example.com/pay": httpx.ConnectError("simulated failure"),
    })
    with pytest.raises(httpx.ConnectError):
        await adapter.post("https://api.example.com/pay", {}, None, 30.0)


@pytest.mark.asyncio
async def test_in_memory_adapter_raises_on_missing_url():
    adapter = InMemoryAdapter({})
    with pytest.raises(KeyError):
        await adapter.post("https://unconfigured.url/pay", {}, None, 30.0)


@pytest.mark.asyncio
async def test_in_memory_adapter_multiple_calls_logged():
    adapter = InMemoryAdapter({
        "https://api.example.com/a": {"a": 1},
        "https://api.example.com/b": {"b": 2},
    })
    await adapter.post("https://api.example.com/a", {}, None, 30.0)
    await adapter.post("https://api.example.com/b", {}, None, 30.0)
    assert len(adapter.calls) == 2
    assert adapter.calls[0]["url"] == "https://api.example.com/a"
    assert adapter.calls[1]["url"] == "https://api.example.com/b"


# ---------------------------------------------------------------------------
# HttpxAdapter unit tests
# ---------------------------------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_httpx_adapter_post_returns_json():
    respx.post("https://api.example.com/pay").mock(
        return_value=httpx.Response(200, json={"result": 100})
    )
    adapter = HttpxAdapter()
    result = await adapter.post("https://api.example.com/pay", {"amount": 1000}, None, 30.0)
    assert result == {"result": 100}


@respx.mock
@pytest.mark.asyncio
async def test_httpx_adapter_get_returns_json():
    respx.get("https://api.example.com/info").mock(
        return_value=httpx.Response(200, json={"data": "ok"})
    )
    adapter = HttpxAdapter()
    result = await adapter.get("https://api.example.com/info", None, None, 30.0)
    assert result == {"data": "ok"}


@respx.mock
@pytest.mark.asyncio
async def test_httpx_adapter_raises_gateway_connection_error_on_timeout():
    respx.post("https://api.example.com/pay").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    adapter = HttpxAdapter(gateway="test_gw")
    with pytest.raises(GatewayConnectionError) as exc_info:
        await adapter.post("https://api.example.com/pay", {}, None, 30.0)
    assert exc_info.value.gateway == "test_gw"


# ---------------------------------------------------------------------------
# Zarinpal gateway with InMemoryAdapter (no respx needed)
# ---------------------------------------------------------------------------

ZARINPAL_REQUEST_URL = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
ZARINPAL_VERIFY_URL = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"


@pytest.fixture
def zarinpal_gateway():
    config = ZarinpalConfig(merchant_id="test-merchant-abc", sandbox=True)
    adapter = InMemoryAdapter({
        ZARINPAL_REQUEST_URL: {
            "data": {"code": 100, "authority": "AUTHORITY-001"},
            "errors": [],
        },
        ZARINPAL_VERIFY_URL: {
            "data": {"code": 100, "ref_id": 555555, "card_pan": "6037****1234"},
            "errors": [],
        },
    })
    return ZarinpalGateway(config, transport=adapter), adapter


@pytest.mark.asyncio
async def test_zarinpal_initiate_with_in_memory_adapter(zarinpal_gateway):
    gw, adapter = zarinpal_gateway
    request = PaymentRequest(
        order_id="ORDER-ADT-001",
        amount=100000,
        callback_url="https://shop.com/verify",
    )
    result = await gw.initiate(request)
    assert result.type == "redirect"
    assert "AUTHORITY-001" in result.url
    assert adapter.calls[0]["url"] == ZARINPAL_REQUEST_URL


@pytest.mark.asyncio
async def test_zarinpal_verify_with_in_memory_adapter(zarinpal_gateway):
    gw, adapter = zarinpal_gateway
    callback = BankCallbackData(
        gateway_slug="zarinpal",
        raw={
            "Authority": "AUTHORITY-001",
            "Status": "OK",
            "_amount": 100000,
            "_order_id": "ORDER-ADT-001",
        },
    )
    result = await gw.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "555555"
    assert result.card_number == "6037****1234"
    assert adapter.calls[0]["url"] == ZARINPAL_VERIFY_URL


# ---------------------------------------------------------------------------
# IDPay gateway with InMemoryAdapter
# ---------------------------------------------------------------------------

IDPAY_PAYMENT_URL = "https://api.idpay.ir/v1.1/payment"
IDPAY_VERIFY_URL = "https://api.idpay.ir/v1.1/payment/verify"


@pytest.fixture
def idpay_gateway():
    config = IDPayConfig(api_key="test-key", sandbox=True)
    adapter = InMemoryAdapter({
        IDPAY_PAYMENT_URL: {"id": "pay-001", "link": "https://idpay.ir/p/pay-001"},
        IDPAY_VERIFY_URL: {
            "status": 100, "track_id": "TRK-001", "payment": {"card_no": "6037****9999"},
        },
    })
    return IDPayGateway(config, transport=adapter), adapter


@pytest.mark.asyncio
async def test_idpay_initiate_with_in_memory_adapter(idpay_gateway):
    gw, adapter = idpay_gateway
    request = PaymentRequest(
        order_id="ORDER-IDP-001",
        amount=50000,
        callback_url="https://shop.com/verify",
    )
    result = await gw.initiate(request)
    assert result.type == "redirect"
    assert "idpay.ir" in result.url


@pytest.mark.asyncio
async def test_idpay_verify_with_in_memory_adapter(idpay_gateway):
    gw, adapter = idpay_gateway
    callback = BankCallbackData(
        gateway_slug="idpay",
        raw={"id": "pay-001", "order_id": "ORDER-IDP-001", "status": 2},
    )
    result = await gw.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "TRK-001"
