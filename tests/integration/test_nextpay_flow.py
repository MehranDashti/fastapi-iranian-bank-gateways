"""Integration tests: NextPay payment gateway flow."""
import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier3.nextpay import NextPayConfig, NextPayGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

NEXTPAY_TOKEN_URL = "https://nextpay.org/nx/gateway/token"
NEXTPAY_VERIFY_URL = "https://nextpay.org/nx/gateway/verify"
_TRANS_ID = "NP-TRANS-001"
_REF_ID = "SHP-NP-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/nextpay",
}


@pytest.fixture
def app():
    gw = NextPayGateway(NextPayConfig(api_key="test-api-key-nextpay"))
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
def test_nextpay_success_flow(client):
    respx.post(NEXTPAY_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"code": -1, "trans_id": _TRANS_ID})
    )
    respx.post(NEXTPAY_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"code": -90, "Shaparak_Ref_Id": _REF_ID})
    )

    resp = client.post("/pay/nextpay", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert _TRANS_ID in resp.headers["location"]

    resp = client.get(
        "/callback/nextpay",
        params={"trans_id": _TRANS_ID, "order_id": "O-001"},
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _REF_ID in resp.headers["location"]


@respx.mock
def test_nextpay_cancelled_flow(client):
    respx.post(NEXTPAY_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"code": -6})
    )

    resp = client.get(
        "/callback/nextpay",
        params={"trans_id": _TRANS_ID, "order_id": "O-001"},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
