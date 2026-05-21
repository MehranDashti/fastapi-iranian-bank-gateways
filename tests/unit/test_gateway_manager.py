from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_iranian_bank_gateways import GatewayManager
from fastapi_iranian_bank_gateways.gateways import IDPayGateway, ZarinpalGateway
from fastapi_iranian_bank_gateways.gateways.tier3.idpay import IDPayConfig
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig


def make_manager(*gateways):
    async def get_order_info(order_id): return {"amount": 100000}
    async def on_success(r): return f"https://shop.com/ok/{r.order_id}"
    async def on_failure(r): return f"https://shop.com/fail/{r.order_id}"

    return GatewayManager(
        gateways=list(gateways),
        get_order_info=get_order_info,
        on_success=on_success,
        on_failure=on_failure,
        prefix="/pay",
    )


_MERCHANT = "test-merchant-00000000000000000"


def test_manager_registers_gateways():
    gw = ZarinpalGateway(ZarinpalConfig(merchant_id=_MERCHANT, sandbox=True))
    manager = make_manager(gw)
    assert "zarinpal" in manager._registry


def test_manager_multiple_gateways():
    gw1 = ZarinpalGateway(ZarinpalConfig(merchant_id=_MERCHANT, sandbox=True))
    gw2 = IDPayGateway(IDPayConfig(api_key="key", sandbox=True))
    manager = make_manager(gw1, gw2)
    assert len(manager._registry) == 2


def test_router_404_on_unknown_gateway():
    gw = ZarinpalGateway(ZarinpalConfig(merchant_id=_MERCHANT, sandbox=True))
    manager = make_manager(gw)
    app = FastAPI()
    app.include_router(manager.router)
    client = TestClient(app, follow_redirects=False)

    resp = client.post("/pay/nonexistent/verify")
    assert resp.status_code == 404


def test_router_has_correct_routes():
    gw = ZarinpalGateway(ZarinpalConfig(merchant_id=_MERCHANT, sandbox=True))
    manager = make_manager(gw)
    routes = {r.path for r in manager.router.routes}
    assert "/pay/{gateway}/pay" in routes
    assert "/pay/{gateway}/verify" in routes
