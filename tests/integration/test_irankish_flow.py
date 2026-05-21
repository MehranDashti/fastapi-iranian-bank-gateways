"""Integration tests: Irankish payment gateway flow."""
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier2.irankish import IrankishConfig, IrankishGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

IRANKISH_TOKEN_URL = "https://ikc.shaparak.ir/TToken/Tokens.ngx"
IRANKISH_VERIFY_URL = "https://ikc.shaparak.ir/TVerify/Verify.ngx"
_TOKEN = "IK-TOKEN-001"
_RRN = "IK-RRN-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/irankish",
}


@pytest.fixture
def app():
    gw = IrankishGateway(
        IrankishConfig(
            terminal_id="IK-TERM",
            acceptor_id="IK-ACCEPT",
            pass_phrase="test-passphrase",
        )
    )
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
def test_irankish_success_flow(client):
    respx.post(IRANKISH_TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"responseCode": "00", "token": _TOKEN}
        )
    )
    respx.post(IRANKISH_VERIFY_URL).mock(
        return_value=httpx.Response(
            200,
            json={"responseCode": "00", "maskedCardNumber": "6037****5678"},
        )
    )

    resp = client.post("/pay/irankish", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert _TOKEN in resp.headers["location"]

    resp = client.post(
        "/callback/irankish",
        data={
            "resultCode": "00",
            "paymentId": "O-001",
            "token": _TOKEN,
            "retrievalReferenceNumber": _RRN,
        },
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _RRN in resp.headers["location"]


def test_irankish_cancelled_flow(client):
    resp = client.post(
        "/callback/irankish",
        data={
            "resultCode": "05",
            "paymentId": "O-001",
            "token": _TOKEN,
            "retrievalReferenceNumber": _RRN,
        },
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
