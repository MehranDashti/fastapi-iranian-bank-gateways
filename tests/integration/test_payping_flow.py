"""Integration tests: PayPing payment gateway flow."""
import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier3.payping import PayPingConfig, PayPingGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

PAYPING_REQUEST_URL = "https://api.payping.ir/v2/pay"
PAYPING_VERIFY_URL = "https://api.payping.ir/v2/pay/verify"
_CODE = "PP-CODE-001"
_REF_ID = "PP-REF-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/payping",
}


@pytest.fixture
def app():
    gw = PayPingGateway(PayPingConfig(access_token="test-access-token"))
    manager = GatewayManager(gateways=[gw])

    application = FastAPI()

    @application.post("/pay/{gw_slug}")
    async def pay(gw_slug: str, req: PaymentRequest):
        return handle_initiate_response(await manager.get(gw_slug).initiate(req))

    @application.get("/callback/{gw_slug}")
    async def callback_get(gw_slug: str, request: Request):
        gateway = manager.get(gw_slug)
        result = await gateway.verify(
            gateway.parse_callback(
                dict(request.query_params),
                amount=100000,
                order_id="O-001",
            )
        )
        if result.status in (PaymentStatus.SUCCESS, PaymentStatus.DUPLICATE):
            return RedirectResponse(f"/success?ref={result.reference_id}", status_code=302)
        return RedirectResponse("/failure", status_code=302)

    return application


@pytest.fixture
def client(app):
    return TestClient(app, follow_redirects=False)


@respx.mock
def test_payping_success_flow(client):
    respx.post(PAYPING_REQUEST_URL).mock(
        return_value=httpx.Response(200, json={"code": _CODE})
    )
    respx.post(PAYPING_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"cardNumber": "6037****1234"})
    )

    resp = client.post("/pay/payping", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert _CODE in resp.headers["location"]

    resp = client.get(
        "/callback/payping",
        params={"refid": _REF_ID, "clientrefid": "O-001"},
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _REF_ID in resp.headers["location"]


@respx.mock
def test_payping_cancelled_flow(client):
    respx.post(PAYPING_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={})
    )

    resp = client.get(
        "/callback/payping",
        params={"refid": _REF_ID, "clientrefid": "O-001"},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
