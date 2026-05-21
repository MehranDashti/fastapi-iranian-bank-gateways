"""
Factory pattern for fastapi-iranian-bank-gateways.

GatewayFactory eliminates the boilerplate of manually importing and
instantiating each gateway class.  It maintains a registry of all 17 built-in
gateways keyed by their slug and offers three construction helpers:

- ``GatewayFactory.create(slug, config)``       — create a single gateway
- ``GatewayFactory.create_all(configs_map)``     — create many from a dict
- ``GatewayFactory.from_env(prefix)``            — create from environment vars

Example — create_all::

    from fastapi_iranian_bank_gateways import GatewayFactory, GatewayManager

    gateways = GatewayFactory.create_all({
        "zarinpal": {"merchant_id": "abc123", "sandbox": True},
        "mellat": {"terminal_id": 12345, "username": "u", "password": "p"},
    })
    manager = GatewayManager(gateways=gateways, ...)

Example — from_env::

    # Set env vars: GATEWAY_ZARINPAL_MERCHANT_ID=abc123 GATEWAY_ZARINPAL_SANDBOX=true
    gateways = GatewayFactory.from_env("GATEWAY_")
    manager = GatewayManager(gateways=gateways, ...)
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from .base.config import BaseGatewayConfig
from .base.gateway import AbstractGateway
from .exceptions.errors import GatewayConfigurationError

# Imported lazily to avoid circular imports at module level — the registry is
# built once on first access via _get_registry().
_REGISTRY_CACHE: dict[str, tuple[type[AbstractGateway], type[BaseGatewayConfig]]] | None = None


def _get_registry() -> dict[str, tuple[type[AbstractGateway], type[BaseGatewayConfig]]]:
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is not None:
        return _REGISTRY_CACHE

    from .gateways.tier1.mellat import MellatConfig, MellatGateway
    from .gateways.tier1.pasargad import PasargadConfig, PasargadGateway
    from .gateways.tier1.saderat import SaderatConfig, SaderatGateway
    from .gateways.tier1.saman import SamanConfig, SamanGateway
    from .gateways.tier1.sepah import SepahConfig, SepahGateway
    from .gateways.tier2.eghtesad_novin import EghtesadNovinConfig, EghtesadNovinGateway
    from .gateways.tier2.irankish import IrankishConfig, IrankishGateway
    from .gateways.tier2.melli import MelliConfig, MelliGateway
    from .gateways.tier2.parsian import ParsianConfig, ParsianGateway
    from .gateways.tier2.tejarat import TejaratConfig, TejaratGateway
    from .gateways.tier3.idpay import IDPayConfig, IDPayGateway
    from .gateways.tier3.nextpay import NextPayConfig, NextPayGateway
    from .gateways.tier3.pay_ir import PayIrConfig, PayIrGateway
    from .gateways.tier3.payping import PayPingConfig, PayPingGateway
    from .gateways.tier3.vandar import VandarConfig, VandarGateway
    from .gateways.tier3.zarinpal import ZarinpalConfig, ZarinpalGateway
    from .gateways.tier3.zibal import ZibalConfig, ZibalGateway

    _REGISTRY_CACHE = {
        "mellat":         (MellatGateway, MellatConfig),
        "saderat":        (SaderatGateway, SaderatConfig),
        "pasargad":       (PasargadGateway, PasargadConfig),
        "saman":          (SamanGateway, SamanConfig),
        "sepah":          (SepahGateway, SepahConfig),
        "parsian":        (ParsianGateway, ParsianConfig),
        "melli":          (MelliGateway, MelliConfig),
        "irankish":       (IrankishGateway, IrankishConfig),
        "tejarat":        (TejaratGateway, TejaratConfig),
        "eghtesad_novin": (EghtesadNovinGateway, EghtesadNovinConfig),
        "zarinpal":       (ZarinpalGateway, ZarinpalConfig),
        "idpay":          (IDPayGateway, IDPayConfig),
        "zibal":          (ZibalGateway, ZibalConfig),
        "nextpay":        (NextPayGateway, NextPayConfig),
        "pay_ir":         (PayIrGateway, PayIrConfig),
        "payping":        (PayPingGateway, PayPingConfig),
        "vandar":         (VandarGateway, VandarConfig),
    }
    return _REGISTRY_CACHE


class GatewayFactory:
    """
    Factory for creating gateway instances from slug + config data.

    The factory maintains a slug → (GatewayClass, ConfigClass) registry for
    all 17 built-in gateways.  Config data can be a plain ``dict`` (validated
    via Pydantic) or an already-constructed ``BaseGatewayConfig`` instance.
    """

    @classmethod
    def available_slugs(cls) -> list[str]:
        """Return the sorted list of all registered gateway slugs."""
        return sorted(_get_registry().keys())

    @classmethod
    def create(
        cls,
        slug: str,
        config: dict[str, Any] | BaseGatewayConfig,
    ) -> AbstractGateway:
        """
        Create a single gateway instance.

        Args:
            slug:   Gateway identifier, e.g. ``"zarinpal"``, ``"mellat"``.
            config: Either a config dict (will be validated via Pydantic) or an
                    already-constructed ``BaseGatewayConfig`` subclass instance.

        Raises:
            GatewayConfigurationError: If the slug is not registered or the
                config dict fails Pydantic validation.
        """
        registry = _get_registry()
        if slug not in registry:
            available = ", ".join(sorted(registry))
            raise GatewayConfigurationError(
                f"Unknown gateway slug '{slug}'. Available: {available}",
                gateway=slug,
            )
        gw_cls, cfg_cls = registry[slug]
        if isinstance(config, dict):
            try:
                config = cfg_cls(**config)
            except Exception as exc:
                raise GatewayConfigurationError(
                    f"Invalid config for gateway '{slug}': {exc}",
                    gateway=slug,
                ) from exc
        return gw_cls(config)

    @classmethod
    def create_all(
        cls,
        configs: Mapping[str, dict[str, Any] | BaseGatewayConfig],
    ) -> list[AbstractGateway]:
        """
        Create multiple gateways from a slug → config mapping.

        Args:
            configs: Mapping of gateway slug to config dict or config instance.

        Returns:
            List of instantiated gateways in the order the mapping provides.
        """
        return [cls.create(slug, cfg) for slug, cfg in configs.items()]

    @classmethod
    def from_env(cls, prefix: str = "GATEWAY_") -> list[AbstractGateway]:
        """
        Auto-discover and create gateways from environment variables.

        Environment variable convention::

            {PREFIX}{SLUG_UPPER}_{FIELD_UPPER}=value

        Examples with prefix ``"GATEWAY_"``::

            GATEWAY_ZARINPAL_MERCHANT_ID=abc123
            GATEWAY_ZARINPAL_SANDBOX=true
            GATEWAY_MELLAT_TERMINAL_ID=12345
            GATEWAY_MELLAT_USERNAME=user
            GATEWAY_MELLAT_PASSWORD=secret

        Boolean env vars: ``"true"``/``"1"``/``"yes"`` → ``True``, anything else → ``False``.
        Integer fields are parsed automatically by Pydantic.

        Raises:
            GatewayConfigurationError: If a detected slug is not registered or
                its config fails validation.
        """
        registry = _get_registry()
        slug_configs: dict[str, dict[str, Any]] = {}

        for key, value in os.environ.items():
            if not key.upper().startswith(prefix.upper()):
                continue
            rest = key[len(prefix):]
            # rest is like "ZARINPAL_MERCHANT_ID" or "MELLAT_TERMINAL_ID"
            # Find the longest matching slug (handles slugs like "eghtesad_novin")
            matched_slug: str | None = None
            for slug in registry:
                if rest.upper().startswith(slug.upper() + "_"):
                    if matched_slug is None or len(slug) > len(matched_slug):
                        matched_slug = slug

            if matched_slug is None:
                continue

            field_name = rest[len(matched_slug) + 1:].lower()
            if matched_slug not in slug_configs:
                slug_configs[matched_slug] = {}
            slug_configs[matched_slug][field_name] = value

        if not slug_configs:
            return []

        return cls.create_all(slug_configs)


__all__ = ["GatewayFactory"]
