"""Integration tests: Saderat Bank (PESI) payment gateway flow."""
import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier1.saderat import SaderatConfig, SaderatGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

SADERAT_TOKEN_URL = "https://mabna.shaparak.ir:8080/V1/PeymentApi/GetToken"
SADERAT_VERIFY_URL = "https://mabna.shaparak.ir:8080/V1/PeymentApi/Advice"
_ACCESS_TOKEN = "SAD-ACCESS-TOK"
_RRN = "SAD-RRN-001"
_DIGITAL_RECEIPT = "SAD-DR-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/saderat",
}


@pytest.fixture
def app():
    gw = SaderatGateway(SaderatConfig(terminal_id="SAD-TERMINAL"))
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
def test_saderat_success_flow(client):
    respx.post(SADERAT_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"Status": 0, "Accesstoken": _ACCESS_TOKEN})
    )
    respx.post(SADERAT_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"Status": "OK"})
    )

    resp = client.post("/pay/saderat", json=_PAYMENT_REQ)
    assert resp.status_code == 200
    assert "<form" in resp.text

    resp = client.get(
        "/callback/saderat",
        params={
            "digitalreceipt": _DIGITAL_RECEIPT,
            "respcode": "0",
            "invoiceid": "O-001",
            "rrn": _RRN,
        },
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _RRN in resp.headers["location"]


def test_saderat_cancelled_flow(client):
    resp = client.get(
        "/callback/saderat",
        params={
            "digitalreceipt": _DIGITAL_RECEIPT,
            "respcode": "99",
            "invoiceid": "O-001",
            "rrn": _RRN,
        },
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
