"""Integration tests: Pasargad Bank (PEP) payment gateway flow."""
import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier1.pasargad import PasargadConfig, PasargadGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

PASARGAD_TOKEN_URL = "https://pep.shaparak.ir/Api/v1/Payment/GetToken"
PASARGAD_PURCHASE_URL = "https://pep.shaparak.ir/Api/v1/Payment/GetUrlAndToken"
PASARGAD_CHECK_URL = "https://pep.shaparak.ir/Api/v1/Payment/CheckTransactionResult"
PASARGAD_VERIFY_URL = "https://pep.shaparak.ir/Api/v1/Payment/VerifyPayment"
_BEARER = "PEP-BEARER-TOK"
_PAY_URL = "https://pep.shaparak.ir/pay?token=PEP-PAY-TOKEN"
_TREF = "PEP-TREF-001"
_URL_ID = "PEP-URL-ID-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/pasargad",
}


@pytest.fixture
def app():
    gw = PasargadGateway(
        PasargadConfig(
            username="test-user",
            password="test-pass",
            terminal_number="PEP-TERMINAL",
            merchant_code="PEP-MERCHANT",
        )
    )
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
def test_pasargad_success_flow(client):
    # Token is fetched on initiate + again on verify (two calls total to token URL)
    respx.post(PASARGAD_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"token": _BEARER})
    )
    respx.post(PASARGAD_PURCHASE_URL).mock(
        return_value=httpx.Response(
            200, json={"resultCode": 0, "data": {"url": _PAY_URL}}
        )
    )
    respx.post(PASARGAD_CHECK_URL).mock(
        return_value=httpx.Response(200, json={"resultCode": 0})
    )
    respx.post(PASARGAD_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"resultCode": 0})
    )

    resp = client.post("/pay/pasargad", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert _PAY_URL == resp.headers["location"]

    resp = client.get(
        "/callback/pasargad",
        params={"iN": "O-001", "tref": _TREF, "iD": _URL_ID},
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _TREF in resp.headers["location"]


@respx.mock
def test_pasargad_cancelled_flow(client):
    respx.post(PASARGAD_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"token": _BEARER})
    )
    respx.post(PASARGAD_CHECK_URL).mock(
        return_value=httpx.Response(200, json={"resultCode": 5})
    )

    resp = client.get(
        "/callback/pasargad",
        params={"iN": "O-001", "tref": _TREF, "iD": _URL_ID},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
