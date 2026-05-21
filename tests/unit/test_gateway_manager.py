import pytest

from fastapi_iranian_bank_gateways import GatewayManager
from fastapi_iranian_bank_gateways.exceptions.errors import GatewayConfigurationError
from fastapi_iranian_bank_gateways.gateways import IDPayGateway, ZarinpalGateway
from fastapi_iranian_bank_gateways.gateways.tier3.idpay import IDPayConfig
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig

_MERCHANT = "test-merchant-00000000000000000"


def make_zarinpal() -> ZarinpalGateway:
    return ZarinpalGateway(ZarinpalConfig(merchant_id=_MERCHANT, sandbox=True))


def make_idpay() -> IDPayGateway:
    return IDPayGateway(IDPayConfig(api_key="test-key", sandbox=True))


def test_manager_registers_single_gateway():
    manager = GatewayManager(gateways=[make_zarinpal()])
    assert "zarinpal" in manager


def test_manager_registers_multiple_gateways():
    manager = GatewayManager(gateways=[make_zarinpal(), make_idpay()])
    assert len(manager._registry) == 2
    assert "zarinpal" in manager
    assert "idpay" in manager


def test_get_returns_correct_gateway():
    gw = make_zarinpal()
    manager = GatewayManager(gateways=[gw])
    assert manager.get("zarinpal") is gw


def test_getitem_returns_correct_gateway():
    gw = make_zarinpal()
    manager = GatewayManager(gateways=[gw])
    assert manager["zarinpal"] is gw


def test_get_unknown_slug_raises_configuration_error():
    manager = GatewayManager(gateways=[make_zarinpal()])
    with pytest.raises(GatewayConfigurationError, match="not registered"):
        manager.get("nonexistent")


def test_get_error_lists_available_gateways():
    manager = GatewayManager(gateways=[make_zarinpal(), make_idpay()])
    with pytest.raises(GatewayConfigurationError, match="zarinpal"):
        manager.get("bogus")


def test_slugs_returns_registered_slugs():
    manager = GatewayManager(gateways=[make_zarinpal(), make_idpay()])
    assert set(manager.slugs()) == {"zarinpal", "idpay"}


def test_contains_operator():
    manager = GatewayManager(gateways=[make_zarinpal()])
    assert "zarinpal" in manager
    assert "mellat" not in manager


@pytest.mark.asyncio
async def test_context_manager_opens_and_closes_client():
    manager = GatewayManager(gateways=[make_zarinpal()])
    assert manager._shared_client is None
    async with manager:
        assert manager._shared_client is not None
    assert manager._shared_client is None
