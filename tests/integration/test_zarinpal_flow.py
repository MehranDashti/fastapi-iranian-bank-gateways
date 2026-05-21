"""Integration tests: full payment flow using developer-owned routes."""
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.adapters import InMemoryAdapter
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig, ZarinpalGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

ZARINPAL_REQUEST_URL = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
ZARINPAL_VERIFY_URL = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
_MERCHANT = "test-merchant-00000000000000000"
_AUTHORITY = "A00000000000000000000000000TESTAUTH"


@pytest.fixture
def app():
    transport = InMemoryAdapter(responses={
        ZARINPAL_REQUEST_URL: {
            "data": {"code": 100, "authority": _AUTHORITY},
            "errors": [],
        },
        ZARINPAL_VERIFY_URL: {
            "data": {"code": 100, "ref_id": 987654, "card_pan": "6037****1234"},
            "errors": [],
        },
    })
    gw = ZarinpalGateway(
        ZarinpalConfig(merchant_id=_MERCHANT, sandbox=True),
        transport=transport,
    )
    manager = GatewayManager(gateways=[gw])

    application = FastAPI()

    @application.post("/pay/{gateway_slug}")
    async def pay(gateway_slug: str, req: PaymentRequest):
        gateway = manager.get(gateway_slug)
        result = await gateway.initiate(req)
        return handle_initiate_response(result)

    @application.get("/callback/{gateway_slug}")
    async def callback_get(gateway_slug: str, request: Request):
        gateway = manager.get(gateway_slug)
        # In a real app: look up order from DB using the authority/token
        # then pass amount and order_id explicitly so the gateway can verify.
        result = await gateway.verify(
            gateway.parse_callback(
                dict(request.query_params),
                amount=100000,    # from developer's DB
                order_id="ORDER-001",  # from developer's DB
            )
        )
        if result.status in (PaymentStatus.SUCCESS, PaymentStatus.DUPLICATE):
            return RedirectResponse(f"/success?ref={result.reference_id}", status_code=302)
        return RedirectResponse(f"/failure?order={result.order_id}", status_code=302)

    @application.post("/callback/{gateway_slug}")
    async def callback_post(gateway_slug: str, request: Request):
        form = await request.form()
        gateway = manager.get(gateway_slug)
        result = await gateway.verify(
            gateway.parse_callback(
                dict(form),
                amount=100000,
                order_id="ORDER-001",
            )
        )
        if result.status in (PaymentStatus.SUCCESS, PaymentStatus.DUPLICATE):
            return RedirectResponse(f"/success?ref={result.reference_id}", status_code=302)
        return RedirectResponse(f"/failure?order={result.order_id}", status_code=302)

    return application


@pytest.fixture
def client(app):
    return TestClient(app, follow_redirects=False)


def test_full_flow_success(client):
    resp = client.post(
        "/pay/zarinpal",
        json={
            "order_id": "ORDER-001",
            "amount": 100000,
            "callback_url": "https://myapp.com/callback/zarinpal",
        },
    )
    assert resp.status_code == 302
    assert _AUTHORITY in resp.headers["location"]

    resp = client.get(
        "/callback/zarinpal",
        params={"Authority": _AUTHORITY, "Status": "OK"},
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert "987654" in resp.headers["location"]


def test_full_flow_cancelled(client):
    resp = client.get(
        "/callback/zarinpal",
        params={"Authority": _AUTHORITY, "Status": "NOK"},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]


def test_manager_get_raises_for_unknown_gateway(client):
    from fastapi_iranian_bank_gateways.exceptions.errors import GatewayConfigurationError

    manager = GatewayManager(gateways=[
        ZarinpalGateway(ZarinpalConfig(merchant_id=_MERCHANT, sandbox=True)),
    ])
    with pytest.raises(GatewayConfigurationError):
        manager.get("nonexistent")
