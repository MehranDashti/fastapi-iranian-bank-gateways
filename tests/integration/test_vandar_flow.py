"""Integration tests: Vandar payment gateway flow."""
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier3.vandar import VandarConfig, VandarGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

VANDAR_SEND_URL = "https://ipg.vandar.io/api/v3/send"
VANDAR_VERIFY_URL = "https://ipg.vandar.io/api/v3/verify"
_TOKEN = "VND-TOK-001"
_TRANS_ID = "VND-TRANS-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/vandar",
}


@pytest.fixture
def app():
    gw = VandarGateway(VandarConfig(api_key="test-api-key-vandar"))
    manager = GatewayManager(gateways=[gw])

    application = FastAPI()

    @application.post("/pay/{gw_slug}")
    async def pay(gw_slug: str, req: PaymentRequest):
        return handle_initiate_response(await manager.get(gw_slug).initiate(req))

    @application.post("/callback/{gw_slug}")
    async def callback_post(gw_slug: str, request: Request):
        body = await request.body()
        form_data = {k: v[0] for k, v in parse_qs(body.decode()).items()}
        gateway = manager.get(gw_slug)
        result = await gateway.verify(
            gateway.parse_callback(form_data, order_id="O-001")
        )
        if result.status in (PaymentStatus.SUCCESS, PaymentStatus.DUPLICATE):
            return RedirectResponse(f"/success?ref={result.reference_id}", status_code=302)
        return RedirectResponse("/failure", status_code=302)

    return application


@pytest.fixture
def client(app):
    return TestClient(app, follow_redirects=False)


@respx.mock
def test_vandar_success_flow(client):
    respx.post(VANDAR_SEND_URL).mock(
        return_value=httpx.Response(200, json={"status": 1, "token": _TOKEN})
    )
    respx.post(VANDAR_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"status": 1, "transId": _TRANS_ID})
    )

    resp = client.post("/pay/vandar", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert _TOKEN in resp.headers["location"]

    resp = client.post(
        "/callback/vandar",
        data={"token": _TOKEN, "payment_status": "DONE", "factorNumber": "O-001"},
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _TRANS_ID in resp.headers["location"]


def test_vandar_cancelled_flow(client):
    resp = client.post(
        "/callback/vandar",
        data={"token": _TOKEN, "payment_status": "FAILED", "factorNumber": "O-001"},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
