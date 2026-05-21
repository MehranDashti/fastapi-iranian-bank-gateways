import logging
from typing import Any

import httpx

from .base.gateway import AbstractGateway
from .exceptions.errors import GatewayConfigurationError

logger = logging.getLogger(__name__)


class GatewayManager:
    """
    Registry of gateways with shared HTTP connection pooling.

    Holds a collection of gateway instances keyed by their slug.  Use
    ``get()`` (or ``manager[slug]``) to retrieve a gateway in a request
    handler, then call ``gateway.initiate()`` / ``gateway.verify()`` directly.

    Use as an async context manager in the FastAPI lifespan to open a single
    shared ``httpx.AsyncClient`` that all gateways borrow during the
    application's lifetime::

        from contextlib import asynccontextmanager
        from fastapi import FastAPI, Request
        from fastapi.responses import RedirectResponse
        from fastapi_iranian_bank_gateways import (
            GatewayManager, GatewayFactory, PaymentRequest, PaymentStatus,
        )
        from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

        manager = GatewayManager(gateways=GatewayFactory.from_env("GATEWAY_"))

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with manager:   # opens shared HTTP client
                yield

        app = FastAPI(lifespan=lifespan)

        @app.post("/pay/{gateway_slug}")
        async def pay(gateway_slug: str, req: PaymentRequest):
            gw = manager.get(gateway_slug)
            result = await gw.initiate(req)
            return handle_initiate_response(result)

        @app.get("/callback/{gateway_slug}")
        async def callback(gateway_slug: str, request: Request):
            gw = manager.get(gateway_slug)
            result = await gw.verify(gw.parse_callback(dict(request.query_params)))
            if result.status == PaymentStatus.SUCCESS:
                return RedirectResponse("/success")
            return RedirectResponse("/failure")
    """

    def __init__(self, gateways: list[AbstractGateway]) -> None:
        self._registry: dict[str, AbstractGateway] = {gw.gateway_slug: gw for gw in gateways}
        self._shared_client: httpx.AsyncClient | None = None

    def get(self, slug: str) -> AbstractGateway:
        """Return the gateway registered under *slug*.

        Raises:
            GatewayConfigurationError: If no gateway with that slug was registered.
        """
        gw = self._registry.get(slug)
        if gw is None:
            available = ", ".join(sorted(self._registry))
            raise GatewayConfigurationError(
                f"Gateway '{slug}' not registered. Available: {available}",
                gateway=slug,
            )
        return gw

    def __getitem__(self, slug: str) -> AbstractGateway:
        return self.get(slug)

    def __contains__(self, slug: object) -> bool:
        return slug in self._registry

    def slugs(self) -> list[str]:
        """Return the list of registered gateway slugs."""
        return list(self._registry.keys())

    async def __aenter__(self) -> "GatewayManager":
        self._shared_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            timeout=30.0,
        )
        logger.info("GatewayManager: shared HTTP client opened")
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._shared_client is not None:
            await self._shared_client.aclose()
            self._shared_client = None
            logger.info("GatewayManager: shared HTTP client closed")


__all__ = ["GatewayManager"]
