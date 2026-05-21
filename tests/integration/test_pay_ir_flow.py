"""Integration tests: Pay.ir payment gateway flow."""
import httpx
import pytest
import respx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier3.pay_ir import PayIrConfig, PayIrGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

PAY_IR_SEND_URL = "https://pay.ir/pg/send"
PAY_IR_VERIFY_URL = "https://pay.ir/pg/verify"
_TOKEN = "PI-TOK-001"
_TRANS_ID = "PI-TRANS-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/pay_ir",
}


@pytest.fixture
def app():
    gw = PayIrGateway(PayIrConfig(api="test-api-key"))
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
            return RedirectResponse(f"/success?ref={result.transaction_id}", status_code=302)
        return RedirectResponse("/failure", status_code=302)

    return application


@pytest.fixture
def client(app):
    return TestClient(app, follow_redirects=False)


@respx.mock
def test_pay_ir_success_flow(client):
    respx.post(PAY_IR_SEND_URL).mock(
        return_value=httpx.Response(200, json={"status": 1, "token": _TOKEN})
    )
    respx.post(PAY_IR_VERIFY_URL).mock(
        return_value=httpx.Response(200, json={"status": 1, "transId": _TRANS_ID})
    )

    resp = client.post("/pay/pay_ir", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert _TOKEN in resp.headers["location"]

    resp = client.get(
        "/callback/pay_ir",
        params={"token": _TOKEN, "status": "1", "factorNumber": "O-001"},
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _TRANS_ID in resp.headers["location"]


def test_pay_ir_cancelled_flow(client):
    resp = client.get(
        "/callback/pay_ir",
        params={"token": _TOKEN, "status": "0", "factorNumber": "O-001"},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
