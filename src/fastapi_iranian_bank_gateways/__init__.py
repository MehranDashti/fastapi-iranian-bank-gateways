"""
fastapi-iranian-bank-gateways
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
FastAPI integration for all major Iranian bank payment gateways.

Supported gateways (17 total):
  Tier 1 — Bank PSPs:    Mellat, Saderat, Pasargad, Saman, Sepah
  Tier 2 — Bank PSPs:    Parsian, Melli, Irankish, Tejarat, EghtesadNovin
  Tier 3 — Fintech:      Zarinpal, IDPay, Zibal, NextPay, PayIr, PayPing, Vandar

Quick start::

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.responses import RedirectResponse
    from fastapi_iranian_bank_gateways import (
        GatewayFactory, GatewayManager, PaymentRequest, PaymentStatus,
    )
    from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

    # Configure gateways from environment variables:
    # GATEWAY_ZARINPAL_MERCHANT_ID=... GATEWAY_ZARINPAL_SANDBOX=true
    manager = GatewayManager(gateways=GatewayFactory.from_env("GATEWAY_"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with manager:   # shared HTTP connection pool
            yield

    app = FastAPI(lifespan=lifespan)

    @app.post("/pay/{gateway_slug}")
    async def pay(gateway_slug: str, req: PaymentRequest):
        gw = manager.get(gateway_slug)
        result = await gw.initiate(req)
        return handle_initiate_response(result)  # RedirectResponse or HTMLResponse

    @app.get("/callback/{gateway_slug}")
    async def callback(gateway_slug: str, request: Request):
        gw = manager.get(gateway_slug)
        result = await gw.verify(gw.parse_callback(dict(request.query_params)))
        if result.status == PaymentStatus.SUCCESS:
            # update your database here
            return RedirectResponse(f"/success?ref={result.reference_id}")
        return RedirectResponse(f"/failure?order={result.order_id}")
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
    handle_initiate_response,
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
    "handle_initiate_response",
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
