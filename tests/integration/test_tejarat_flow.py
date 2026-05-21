"""Integration tests: Tejarat Bank payment gateway flow."""
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier2.tejarat import TejaratConfig, TejaratGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

TEJARAT_TOKEN_URL = "https://agt.tejaratpay.com/ipg/api/v1/token"
TEJARAT_VERIFY_URL = "https://agt.tejaratpay.com/ipg/api/v1/payment"
_TOKEN = "TEJ-TOKEN-001"
_TRACE = "TRC-TEJ-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/tejarat",
}


@pytest.fixture
def app():
    gw = TejaratGateway(TejaratConfig(terminal_id="TEJ-TERMINAL"))
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
def test_tejarat_success_flow(client):
    respx.post(TEJARAT_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"token": _TOKEN})
    )
    respx.post(TEJARAT_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"status": "0", "traceNumber": _TRACE})
    )

    resp = client.post("/pay/tejarat", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert _TOKEN in resp.headers["location"]

    resp = client.post(
        "/callback/tejarat",
        data={"status": "0", "token": _TOKEN, "invoiceNumber": "O-001"},
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _TRACE in resp.headers["location"]


def test_tejarat_cancelled_flow(client):
    resp = client.post(
        "/callback/tejarat",
        data={"status": "5", "token": _TOKEN, "invoiceNumber": "O-001"},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
