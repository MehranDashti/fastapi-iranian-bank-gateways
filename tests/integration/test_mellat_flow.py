"""Integration tests: Mellat Bank (Behpardakht Mellat) SOAP payment gateway flow."""
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.gateways.tier1.mellat import MellatConfig, MellatGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

MELLAT_SOAP_PATH = (
    "fastapi_iranian_bank_gateways.gateways.tier1.mellat.gateway.get_soap_client"
)
_TOKEN = "MELLAT-TOKEN-001"
_REF = "MELLAT-REF-001"

_PAYMENT_REQ = {
    "order_id": "12345",
    "amount": 100000,
    "callback_url": "https://myapp.com/callback/mellat",
}


@pytest.fixture
def app():
    gw = MellatGateway(
        MellatConfig(terminal_id=12345678, username="test-user", password="test-pass")
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
            gateway.parse_callback(form_data, order_id="12345")
        )
        if result.status in (PaymentStatus.SUCCESS, PaymentStatus.DUPLICATE):
            return RedirectResponse(f"/success?ref={result.reference_id}", status_code=302)
        return RedirectResponse("/failure", status_code=302)

    return application


@pytest.fixture
def client(app):
    return TestClient(app, follow_redirects=False)


def test_mellat_success_flow(client):
    mock_soap = MagicMock()
    mock_soap.service.bpPayRequest.return_value = f"0,{_TOKEN}"
    mock_soap.service.bpVerifyRequest.return_value = "0"

    with patch(MELLAT_SOAP_PATH, return_value=mock_soap):
        resp = client.post("/pay/mellat", json=_PAYMENT_REQ)
    assert resp.status_code == 200
    assert "<form" in resp.text

    with patch(MELLAT_SOAP_PATH, return_value=mock_soap):
        resp = client.post(
            "/callback/mellat",
            data={"ResCode": "0", "SaleOrderId": "12345", "SaleReferenceId": _REF},
        )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert _REF in resp.headers["location"]


def test_mellat_cancelled_flow(client):
    resp = client.post(
        "/callback/mellat",
        data={"ResCode": "21", "SaleOrderId": "12345", "SaleReferenceId": _REF},
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]
