"""
fastapi-iranian-bank-gateways
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
FastAPI integration for all major Iranian bank payment gateways.

Supported gateways (17 total):
  Tier 1 — Bank PSPs:    Mellat, Saderat, Pasargad, Saman, Sepah
  Tier 2 — Bank PSPs:    Parsian, Melli, Irankish, Tejarat, EghtesadNovin
  Tier 3 — Fintech:      Zarinpal, IDPay, Zibal, NextPay, PayIr, PayPing, Vandar

Quick start::

    from fastapi import FastAPI
    from fastapi_iranian_bank_gateways import GatewayManager
    from fastapi_iranian_bank_gateways.gateways import ZarinpalGateway
    from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig

    app = FastAPI()
    manager = GatewayManager(
        gateways=[ZarinpalGateway(ZarinpalConfig(merchant_id="...", sandbox=True))],
        get_order_info=lambda oid: {"amount": 50000},
        on_success=lambda r: f"https://shop.com/success/{r.order_id}",
        on_failure=lambda r: f"https://shop.com/failed/{r.order_id}",
    )
    app.include_router(manager.router, prefix="/payments")
"""

from .adapters import HttpTransportAdapter, HttpxAdapter, InMemoryAdapter
from .base.config import BaseGatewayConfig
from .base.gateway import AbstractGateway
from .exceptions.errors import (
    DuplicatePaymentError,
    GatewayAuthError,
    GatewayConfigurationError,
    GatewayConnectionError,
    GatewayError,
    GatewayPaymentError,
    MissingDependencyError,
    OrderNotFoundError,
)
from .factory import GatewayFactory
from .manager import GatewayManager
from .models.callback import BankCallbackData, PaymentResult
from .models.enums import Currency, GatewayType, PaymentStatus
from .models.payment import (
    FormInitiateResponse,
    InitiateResponse,
    PaymentRequest,
    RedirectInitiateResponse,
)
from .strategies import (
    ExponentialBackoffStrategy,
    FormInitiateStrategy,
    InitiateResponseStrategy,
    LinearBackoffStrategy,
    NoRetryStrategy,
    RedirectInitiateStrategy,
    RetryStrategy,
)

__version__ = "0.1.0"

__all__ = [
    # Manager
    "GatewayManager",
    # Factory
    "GatewayFactory",
    # Models
    "PaymentRequest",
    "FormInitiateResponse",
    "RedirectInitiateResponse",
    "InitiateResponse",
    "BankCallbackData",
    "PaymentResult",
    # Enums
    "PaymentStatus",
    "Currency",
    "GatewayType",
    # Exceptions
    "GatewayError",
    "GatewayConfigurationError",
    "GatewayConnectionError",
    "GatewayAuthError",
    "GatewayPaymentError",
    "MissingDependencyError",
    "OrderNotFoundError",
    "DuplicatePaymentError",
    # Base classes
    "AbstractGateway",
    "BaseGatewayConfig",
    # Strategies
    "InitiateResponseStrategy",
    "FormInitiateStrategy",
    "RedirectInitiateStrategy",
    "RetryStrategy",
    "NoRetryStrategy",
    "ExponentialBackoffStrategy",
    "LinearBackoffStrategy",
    # Adapters
    "HttpTransportAdapter",
    "HttpxAdapter",
    "InMemoryAdapter",
]
