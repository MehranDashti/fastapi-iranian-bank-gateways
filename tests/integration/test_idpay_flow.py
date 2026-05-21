"""Integration tests: IDPay payment gateway flow."""
from urllib.parse import parse_qs

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.adapters import InMemoryAdapter
from fastapi_iranian_bank_gateways.gateways.tier3.idpay import IDPayConfig, IDPayGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

IDPAY_PAYMENT_URL = "https://api.idpay.ir/v1.1/payment"
IDPAY_VERIFY_URL = "https://api.idpay.ir/v1.1/payment/verify"
_API_KEY = "test-api-key-idpay"
_PAYMENT_ID = "PAY-IDPAY-001"
_TRACK_ID = "TRK-IDPAY-001"
_LINK = "https://idpay.ir/p/ws/PAY-IDPAY-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/idpay",
}


@pytest.fixture
def app():
    transport = InMemoryAdapter(responses={
        IDPAY_PAYMENT_URL: {"id": _PAYMENT_ID, "link": _LINK},
        IDPAY_VERIFY_URL: {"status": 100, "track_id": _TRACK_ID},
    })
    gw = IDPayGateway(IDPayConfig(api_key=_API_KEY), transport=transport)
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


def test_idpay_success_flow(client):
    resp = client.post("/pay/idpay", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert _LINK in resp.headers["location"]

    resp = client.post(
        "/callback/idpay",
        data={"id": _PAYMENT_ID, "order_id": "O-001", "status": "100"},
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _TRACK_ID in resp.headers["location"]


def test_idpay_cancelled_flow(client):
    resp = client.post(
        "/callback/idpay",
        data={"id": _PAYMENT_ID, "order_id": "O-001", "status": "7"},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
