"""Integration tests: Bank Melli (Behpardakht) payment gateway flow."""
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier2.melli import MelliConfig, MelliGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

MELLI_TOKEN_URL = "https://bpms.bpi.ir/pgwchannel/services/rest/PaymentTokenRequest"
MELLI_VERIFY_URL = "https://bpms.bpi.ir/pgwchannel/services/rest/VerifyPayment"
_TOKEN = "MELLI-TOKEN-001"
_REF = "MELLI-REF-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/melli",
}


@pytest.fixture
def app():
    gw = MelliGateway(
        MelliConfig(terminal_id="12345678", merchant_id="TEST-MERCHANT", sandbox=True)
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
def test_melli_success_flow(client):
    respx.post(MELLI_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"ResCode": "0", "Token": _TOKEN})
    )
    respx.post(MELLI_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"ResCode": "0"})
    )

    resp = client.post("/pay/melli", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert _TOKEN in resp.headers["location"]

    resp = client.post(
        "/callback/melli",
        data={"ResCode": "0", "OrderId": "O-001", "SaleReferenceId": _REF},
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _REF in resp.headers["location"]


def test_melli_cancelled_flow(client):
    resp = client.post(
        "/callback/melli",
        data={"ResCode": "21", "OrderId": "O-001", "SaleReferenceId": _REF},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
