"""Integration tests: Eghtesad Novin Bank payment gateway flow."""
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier2.eghtesad_novin import (
    EghtesadNovinConfig,
    EghtesadNovinGateway,
)
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

EN_TOKEN_URL = "https://ipg.en-bank.ir/igprest/api/v1/merchants/token"
EN_PAYMENT_URL = "https://ipg.en-bank.ir/igprest/api/v1/merchants/payment"
EN_VERIFY_URL = "https://ipg.en-bank.ir/igprest/api/v1/merchants/verify"
_AUTH_TOKEN = "EN-AUTH-TOK"
_PAY_TOKEN = "EN-PAY-TOK"
_RRN = "EN-REF-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/eghtesad_novin",
}


@pytest.fixture
def app():
    gw = EghtesadNovinGateway(
        EghtesadNovinConfig(
            username="test-user",
            password="test-pass",
            merchant_id="EN-MERCHANT",
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
def test_eghtesad_novin_success_flow(client):
    # Token endpoint is called twice: once for initiate, once for verify
    respx.post(EN_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"Token": _AUTH_TOKEN})
    )
    respx.post(EN_PAYMENT_URL).mock(
        return_value=httpx.Response(200, json={"Token": _PAY_TOKEN})
    )
    respx.post(EN_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"Status": "0", "RRN": _RRN})
    )

    resp = client.post("/pay/eghtesad_novin", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert _PAY_TOKEN in resp.headers["location"]

    resp = client.post(
        "/callback/eghtesad_novin",
        data={"Status": "0", "Token": _PAY_TOKEN, "OrderId": "O-001"},
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _RRN in resp.headers["location"]


def test_eghtesad_novin_cancelled_flow(client):
    resp = client.post(
        "/callback/eghtesad_novin",
        data={"Status": "1", "Token": _PAY_TOKEN, "OrderId": "O-001"},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
