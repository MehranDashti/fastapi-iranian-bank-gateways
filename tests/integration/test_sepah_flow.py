"""Integration tests: Sepah Bank SOAP payment gateway flow."""
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier1.sepah import SepahConfig, SepahGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

SEPAH_SOAP_PATH = (
    "fastapi_iranian_bank_gateways.gateways.tier1.sepah.gateway.get_soap_client"
)
_TOKEN = "SEPAH-TOKEN-001"
_RRN = "SEPAH-RRN-001"

_PAYMENT_REQ = {
    "order_id": "O-001",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/sepah",
}


@pytest.fixture
def app():
    gw = SepahGateway(SepahConfig(login_account="test-login-account"))
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


def test_sepah_success_flow(client):
    mock_soap = MagicMock()
    mock_soap.service.SalePaymentRequest.return_value = {"Status": 0, "Token": _TOKEN}
    mock_soap.service.ConfirmPayment.return_value = {
        "Status": "0",
        "RRN": _RRN,
        "CardNumberMasked": "6037****9999",
    }

    with patch(SEPAH_SOAP_PATH, return_value=mock_soap):
        resp = client.post("/pay/sepah", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert _TOKEN in resp.headers["location"]

    with patch(SEPAH_SOAP_PATH, return_value=mock_soap):
        resp = client.post(
            "/callback/sepah",
            data={"status": "1", "Token": _TOKEN, "OrderId": "O-001"},
        )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _RRN in resp.headers["location"]


def test_sepah_cancelled_flow(client):
    resp = client.post(
        "/callback/sepah",
        data={"status": "0", "Token": _TOKEN, "OrderId": "O-001"},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
