import os

import pytest

from fastapi_iranian_bank_gateways import GatewayFactory
from fastapi_iranian_bank_gateways.exceptions import GatewayConfigurationError
from fastapi_iranian_bank_gateways.gateways import IDPayGateway, MellatGateway, ZarinpalGateway


def test_available_slugs_contains_all_17():
    slugs = GatewayFactory.available_slugs()
    assert len(slugs) == 17
    assert "zarinpal" in slugs
    assert "mellat" in slugs
    assert "eghtesad_novin" in slugs


def test_create_single_gateway_from_dict():
    gw = GatewayFactory.create("zarinpal", {"merchant_id": "abc123", "sandbox": True})
    assert isinstance(gw, ZarinpalGateway)
    assert gw.config.merchant_id == "abc123"
    assert gw.config.sandbox is True


def test_create_single_gateway_from_config_instance():
    from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig
    config = ZarinpalConfig(merchant_id="abc123")
    gw = GatewayFactory.create("zarinpal", config)
    assert isinstance(gw, ZarinpalGateway)
    assert gw.config is config


def test_create_mellat_from_dict():
    gw = GatewayFactory.create("mellat", {
        "terminal_id": 12345,
        "username": "user",
        "password": "pass",
    })
    assert isinstance(gw, MellatGateway)
    assert gw.config.terminal_id == 12345


def test_create_unknown_slug_raises():
    with pytest.raises(GatewayConfigurationError) as exc_info:
        GatewayFactory.create("unknown_bank", {})
    assert "unknown_bank" in str(exc_info.value)


def test_create_bad_config_raises():
    with pytest.raises(GatewayConfigurationError):
        GatewayFactory.create("zarinpal", {})  # merchant_id is required


def test_create_all_returns_multiple_gateways():
    gateways = GatewayFactory.create_all({
        "zarinpal": {"merchant_id": "abc"},
        "idpay": {"api_key": "key123"},
    })
    assert len(gateways) == 2
    assert any(isinstance(gw, ZarinpalGateway) for gw in gateways)
    assert any(isinstance(gw, IDPayGateway) for gw in gateways)


def test_create_all_empty_mapping():
    assert GatewayFactory.create_all({}) == []


def test_create_all_preserves_order():
    slugs_in = ["zibal", "nextpay", "pay_ir"]
    gateways = GatewayFactory.create_all({
        "zibal": {"merchant": "zibal"},
        "nextpay": {"api_key": "key"},
        "pay_ir": {"api": "test"},
    })
    for gw, slug in zip(gateways, slugs_in):
        assert gw.gateway_slug == slug


def test_from_env_discovers_zarinpal(monkeypatch):
    monkeypatch.setenv("GATEWAY_ZARINPAL_MERCHANT_ID", "env-merchant-id")
    monkeypatch.setenv("GATEWAY_ZARINPAL_SANDBOX", "true")
    gateways = GatewayFactory.from_env("GATEWAY_")
    assert len(gateways) == 1
    assert isinstance(gateways[0], ZarinpalGateway)
    assert gateways[0].config.merchant_id == "env-merchant-id"


def test_from_env_no_vars_returns_empty(monkeypatch):
    # Ensure no GATEWAY_ env vars exist
    for key in list(os.environ.keys()):
        if key.upper().startswith("GATEWAY_"):
            monkeypatch.delenv(key, raising=False)
    gateways = GatewayFactory.from_env("GATEWAY_")
    assert gateways == []


def test_from_env_custom_prefix(monkeypatch):
    monkeypatch.setenv("MYAPP_IDPAY_API_KEY", "mykey")
    gateways = GatewayFactory.from_env("MYAPP_")
    assert len(gateways) == 1
    assert isinstance(gateways[0], IDPayGateway)
    assert gateways[0].config.api_key == "mykey"


def test_from_env_multi_gateway(monkeypatch):
    monkeypatch.setenv("GW_ZARINPAL_MERCHANT_ID", "zid")
    monkeypatch.setenv("GW_IDPAY_API_KEY", "ikey")
    gateways = GatewayFactory.from_env("GW_")
    slugs = {gw.gateway_slug for gw in gateways}
    assert "zarinpal" in slugs
    assert "idpay" in slugs
