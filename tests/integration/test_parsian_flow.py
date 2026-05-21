"""Integration tests: Parsian Bank SOAP payment gateway flow."""
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier2.parsian import ParsianConfig, ParsianGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

PARSIAN_SOAP_PATH = (
    "fastapi_iranian_bank_gateways.gateways.tier2.parsian.gateway.get_soap_client"
)
_TOKEN = 987654
_RRN = "RRN-PAR-001"

_PAYMENT_REQ = {
    "order_id": "12345",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/parsian",
}


@pytest.fixture
def app():
    gw = ParsianGateway(ParsianConfig(login_account="test-login-account"))
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
            gateway.parse_callback(form_data, order_id="12345")
        )
        if result.status in (PaymentStatus.SUCCESS, PaymentStatus.DUPLICATE):
            return RedirectResponse(f"/success?ref={result.reference_id}", status_code=302)
        return RedirectResponse("/failure", status_code=302)

    return application


@pytest.fixture
def client(app):
    return TestClient(app, follow_redirects=False)


def test_parsian_success_flow(client):
    mock_sale = MagicMock()
    mock_sale.service.SalePaymentRequest.return_value = {"Status": 0, "Token": _TOKEN}

    mock_confirm = MagicMock()
    mock_confirm.service.ConfirmPayment.return_value = {"Status": 0, "RRN": _RRN}

    def soap_factory(wsdl_url: str):
        if "Sale" in wsdl_url:
            return mock_sale
        return mock_confirm

    with patch(PARSIAN_SOAP_PATH, side_effect=soap_factory):
        resp = client.post("/pay/parsian", json=_PAYMENT_REQ)
    assert resp.status_code == 302
    assert str(_TOKEN) in resp.headers["location"]

    with patch(PARSIAN_SOAP_PATH, side_effect=soap_factory):
        resp = client.post(
            "/callback/parsian",
            data={"status": "0", "Token": str(_TOKEN), "OrderId": "12345", "RRN": _RRN},
        )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _RRN in resp.headers["location"]


def test_parsian_cancelled_flow(client):
    resp = client.post(
        "/callback/parsian",
        data={"status": "-1", "Token": str(_TOKEN), "OrderId": "12345", "RRN": _RRN},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
