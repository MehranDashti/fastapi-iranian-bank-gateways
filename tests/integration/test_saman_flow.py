"""Integration tests: Saman Bank (SEP) payment gateway flow."""
import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier1.saman import SamanConfig, SamanGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

SAMAN_TOKEN_URL = "https://sep.shaparak.ir/onlinepg/onlinepg"
SAMAN_VERIFY_URL = "https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction"
_TOKEN = "SAM-TOKEN-001"
_REF_NUM = "SAM-REF-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/saman",
}


@pytest.fixture
def app():
    gw = SamanGateway(SamanConfig(terminal_id="SAM-TERMINAL", password="test-pass"))
    manager = GatewayManager(gateways=[gw])

    application = FastAPI()

    @application.post("/pay/{gw_slug}")
    async def pay(gw_slug: str, req: PaymentRequest):
        return handle_initiate_response(await manager.get(gw_slug).initiate(req))

    @application.get("/callback/{gw_slug}")
    async def callback_get(gw_slug: str, request: Request):
        gateway = manager.get(gw_slug)
        result = await gateway.verify(
            gateway.parse_callback(dict(request.query_params), order_id="O-001")
        )
        if result.status in (PaymentStatus.SUCCESS, PaymentStatus.DUPLICATE):
            return RedirectResponse(f"/success?ref={result.reference_id}", status_code=302)
        return RedirectResponse("/failure", status_code=302)

    return application


@pytest.fixture
def client(app):
    return TestClient(app, follow_redirects=False)


@respx.mock
def test_saman_success_flow(client):
    respx.post(SAMAN_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"status": 1, "token": _TOKEN})
    )
    respx.post(SAMAN_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"Success": True, "ResultCode": 0})
    )

    resp = client.post("/pay/saman", json=_PAYMENT_REQ)
    assert resp.status_code == 200
    assert "<form" in resp.text

    resp = client.get(
        "/callback/saman",
        params={"State": "OK", "RefNum": _REF_NUM, "ResNum": "O-001"},
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _REF_NUM in resp.headers["location"]


def test_saman_cancelled_flow(client):
    resp = client.get(
        "/callback/saman",
        params={"State": "CANCEL", "RefNum": _REF_NUM, "ResNum": "O-001"},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
