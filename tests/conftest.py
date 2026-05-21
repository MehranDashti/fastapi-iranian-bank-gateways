import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager, PaymentResult
from fastapi_iranian_bank_gateways.gateways import ZarinpalGateway
from fastapi_iranian_bank_gateways.gateways.tier1.saderat import SaderatConfig
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig


@pytest.fixture
def zarinpal_config():
    return ZarinpalConfig(merchant_id="test-merchant-id-1234-5678-9012", sandbox=True)


@pytest.fixture
def saderat_config():
    return SaderatConfig(terminal_id="test_terminal")


@pytest.fixture
def test_app(zarinpal_config):
    app = FastAPI()

    async def get_order_info(order_id: str) -> dict:
        return {"amount": 100000, "description": f"Order {order_id}"}

    async def on_success(result: PaymentResult) -> str:
        return f"https://shop.com/success/{result.order_id}"

    async def on_failure(result: PaymentResult) -> str:
        return f"https://shop.com/failed/{result.order_id}"

    manager = GatewayManager(
        gateways=[ZarinpalGateway(zarinpal_config)],
        get_order_info=get_order_info,
        on_success=on_success,
        on_failure=on_failure,
        prefix="/payments",
    )
    app.include_router(manager.router)
    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app, follow_redirects=False)
