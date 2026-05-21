"""Integration tests: full request-response cycle through the FastAPI router."""
import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager
from fastapi_iranian_bank_gateways.gateways import ZarinpalGateway
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig
from fastapi_iranian_bank_gateways.models.callback import PaymentResult

PAYMENT_URL = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
VERIFY_URL = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
SUCCESS_URL = "https://shop.com/order/success"
FAILURE_URL = "https://shop.com/order/failure"


async def get_order_info(order_id: str) -> dict:
    return {"amount": 100000, "description": f"Order {order_id}"}


async def on_success(result: PaymentResult) -> str:
    return f"{SUCCESS_URL}?ref={result.reference_id}"


async def on_failure(result: PaymentResult) -> str:
    return f"{FAILURE_URL}?order={result.order_id}"


@pytest.fixture
def app():
    gw = ZarinpalGateway(ZarinpalConfig(
        merchant_id="test-merchant-00000000000000000000",
        sandbox=True,
    ))
    manager = GatewayManager(
        gateways=[gw],
        get_order_info=get_order_info,
        on_success=on_success,
        on_failure=on_failure,
    )
    application = FastAPI()
    application.include_router(manager.router, prefix="/payments")
    return application


@pytest.fixture
def client(app):
    return TestClient(app, follow_redirects=False)


@respx.mock
def test_full_flow_success(client):
    # Step 1: initiate
    respx.post(PAYMENT_URL).mock(
        return_value=httpx.Response(200, json={
            "data": {"code": 100, "authority": "A00000000000000000000000000TESTAUTH"},
            "errors": [],
        })
    )
    resp = client.post(
        "/payments/zarinpal/pay",
        json={
            "order_id": "ORDER-INT-001",
            "amount": 100000,
            "callback_url": "https://shop.com/payments/zarinpal/verify",
        },
    )
    assert resp.status_code == 302
    assert "A00000000000000000000000000TESTAUTH" in resp.headers["location"]

    # Step 2: bank redirects back — verify
    respx.post(VERIFY_URL).mock(
        return_value=httpx.Response(200, json={
            "data": {"code": 100, "ref_id": 987654, "card_pan": "6037****1234"},
            "errors": [],
        })
    )
    resp = client.get(
        "/payments/zarinpal/verify",
        params={
            "Authority": "A00000000000000000000000000TESTAUTH",
            "Status": "OK",
            "order_id": "ORDER-INT-001",
        },
    )
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
    assert "987654" in resp.headers["location"]


@respx.mock
def test_full_flow_cancelled(client):
    resp = client.get(
        "/payments/zarinpal/verify",
        params={
            "Authority": "A00000000000000000000000000TESTAUTH",
            "Status": "NOK",
            "order_id": "ORDER-INT-002",
        },
    )
    assert resp.status_code == 302
    assert "failure" in resp.headers["location"]


def test_unknown_gateway_returns_404(client):
    resp = client.post(
        "/payments/unknown_gw/pay",
        json={
            "order_id": "ORDER-INT-003",
            "amount": 50000,
            "callback_url": "https://shop.com/verify",
        },
    )
    assert resp.status_code == 404


def test_unknown_gateway_verify_returns_404(client):
    resp = client.get("/payments/unknown_gw/verify", params={"Status": "OK"})
    assert resp.status_code == 404
