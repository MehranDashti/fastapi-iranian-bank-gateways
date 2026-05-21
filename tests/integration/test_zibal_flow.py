"""Integration tests: Zibal payment gateway flow."""
import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier3.zibal import ZibalConfig, ZibalGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

ZIBAL_REQUEST_URL = "https://gateway.zibal.ir/v1/request"
ZIBAL_VERIFY_URL = "https://gateway.zibal.ir/v1/verify"
_TRACK_ID = "456789"
_REF_NUMBER = "REF-Z01"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/zibal",
}


@pytest.fixture
def app():
    gw = ZibalGateway(ZibalConfig(merchant="zibal"))
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
def test_zibal_success_flow(client):
    respx.post(ZIBAL_REQUEST_URL).mock(
        return_value=httpx.Response(200, json={"result": 100, "trackId": int(_TRACK_ID)})
    )
    respx.post(ZIBAL_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"result": 100, "refNumber": _REF_NUMBER})
    )

    resp = client.post("/pay/zibal", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert _TRACK_ID in resp.headers["location"]

    resp = client.get(
        "/callback/zibal",
        params={"trackId": _TRACK_ID, "success": "1", "orderId": "O-001"},
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _REF_NUMBER in resp.headers["location"]


def test_zibal_cancelled_flow(client):
    resp = client.get(
        "/callback/zibal",
        params={"trackId": _TRACK_ID, "success": "0", "orderId": "O-001"},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
