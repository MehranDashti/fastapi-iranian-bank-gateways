import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from .base.gateway import AbstractGateway
from .models.callback import PaymentResult
from .models.enums import PaymentStatus
from .models.payment import PaymentRequest
from .strategies import handle_initiate_response

logger = logging.getLogger(__name__)

GetOrderInfoFn = Callable[[str], Awaitable[dict[str, Any]]]
OnSuccessFn = Callable[[PaymentResult], Awaitable[str]]
OnFailureFn = Callable[[PaymentResult], Awaitable[str]]


class GatewayManager:
    """
    Registers multiple gateways and exposes a FastAPI router with unified payment routes.

    Usage::

        manager = GatewayManager(
            gateways=[MellatGateway(config), ZarinpalGateway(config)],
            get_order_info=my_get_order_info,
            on_success=my_on_success,
            on_failure=my_on_failure,
        )
        app.include_router(manager.router, prefix="/payments")

    For connection pooling, use as an async context manager in the FastAPI lifespan::

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with manager:
                yield

    Generated routes:
        POST /{gateway}/pay        — initiate payment
        GET  /{gateway}/verify     — bank GET callback
        POST /{gateway}/verify     — bank POST callback
    """

    def __init__(
        self,
        gateways: list[AbstractGateway],
        get_order_info: GetOrderInfoFn,
        on_success: OnSuccessFn,
        on_failure: OnFailureFn,
        prefix: str = "",
        tags: list[str] | None = None,
    ) -> None:
        self._registry: dict[str, AbstractGateway] = {}
        self._get_order_info = get_order_info
        self._on_success = on_success
        self._on_failure = on_failure
        self._shared_client: httpx.AsyncClient | None = None

        for gw in gateways:
            self._registry[gw.gateway_slug] = gw

        self.router = self._build_router(prefix, tags or ["payments"])

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

    def _build_router(self, prefix: str, tags: Sequence[str]) -> APIRouter:
        router = APIRouter(prefix=prefix, tags=list(tags))

        @router.post("/{gateway}/pay", summary="Initiate payment")
        async def initiate_payment(
            gateway: str, request: PaymentRequest, http_request: Request
        ) -> Response:
            request_id = http_request.headers.get("X-Request-ID", str(uuid.uuid4()))
            gw = self._resolve(gateway)
            logger.info(
                "Payment initiate: gateway=%s order_id=%s request_id=%s",
                gateway, request.order_id, request_id,
            )
            result = await gw.initiate(request)
            return handle_initiate_response(result)

        @router.get("/{gateway}/verify", summary="Bank GET callback")
        async def verify_get(gateway: str, request: Request) -> RedirectResponse:
            return await self._handle_verify(gateway, request)

        @router.post("/{gateway}/verify", summary="Bank POST callback")
        async def verify_post(gateway: str, request: Request) -> RedirectResponse:
            return await self._handle_verify(gateway, request)

        return router

    async def _handle_verify(self, gateway: str, request: Request) -> RedirectResponse:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        gw = self._resolve(gateway)

        raw: dict[str, Any] = dict(request.query_params)
        if request.method == "POST":
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.json()
                raw.update(body if isinstance(body, dict) else {})
            else:
                form = await request.form()
                raw.update(dict(form))

        order_id = self._extract_order_id(gw.gateway_slug, raw)
        if order_id:
            try:
                order_info = await self._get_order_info(order_id)
                raw["_amount"] = order_info.get("amount")
                raw["_order_id"] = order_id
            except Exception as exc:
                logger.warning(
                    "Payment verify: gateway=%s order_id=%s request_id=%s "
                    "get_order_info failed: %s",
                    gateway, order_id, request_id, exc,
                )

        callback_data = gw.parse_callback(raw)
        result = await gw.verify(callback_data)

        logger.info(
            "Payment verify: gateway=%s order_id=%s status=%s error_code=%s request_id=%s",
            gateway, result.order_id, result.status.value,
            result.error_code, request_id,
        )

        if result.status in (PaymentStatus.SUCCESS, PaymentStatus.DUPLICATE):
            redirect_url = await self._on_success(result)
        else:
            redirect_url = await self._on_failure(result)

        return RedirectResponse(url=redirect_url, status_code=302)

    def _resolve(self, slug: str) -> AbstractGateway:
        gw = self._registry.get(slug)
        if gw is None:
            raise HTTPException(status_code=404, detail=f"Gateway '{slug}' not registered")
        return gw

    @staticmethod
    def _extract_order_id(gateway_slug: str, raw: dict[str, Any]) -> str | None:
        """Best-effort extraction of order_id from callback params."""
        candidates = [
            "order_id", "orderId", "OrderId", "SaleOrderId",
            "iN", "ResNum", "invoice_id",
        ]
        for key in candidates:
            val = raw.get(key)
            if val:
                return str(val)
        return None
