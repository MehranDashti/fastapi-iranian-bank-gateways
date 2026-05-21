"""
Adapter pattern implementations for fastapi-iranian-bank-gateways.

HttpTransportAdapter is a Protocol that defines the async HTTP interface used by
gateways.  Two concrete adapters are provided:

- HttpxAdapter  — production default; wraps httpx, supports connection pooling
                  and an injected RetryStrategy.
- InMemoryAdapter — lightweight test double; returns pre-configured responses
                    without any real network calls.  Logs all calls for assertion.

Usage — production::

    adapter = HttpxAdapter()                        # creates its own client
    gw = ZarinpalGateway(config, transport=adapter)

Usage — with connection pool::

    async with httpx.AsyncClient(...) as client:
        adapter = HttpxAdapter(client=client)
        gw = ZarinpalGateway(config, transport=adapter)

Usage — tests::

    adapter = InMemoryAdapter({
        "https://sandbox.zarinpal.com/pg/v4/payment/request.json": {
            "data": {"code": 100, "authority": "AUTH123"},
            "errors": [],
        },
    })
    gw = ZarinpalGateway(config, transport=adapter)
    await gw.initiate(request)
    assert adapter.calls[0]["url"] == "https://..."
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import httpx

from .exceptions.errors import GatewayConnectionError
from .strategies import NoRetryStrategy, RetryStrategy

_RETRYABLE = (httpx.TimeoutException, httpx.NetworkError)


# ---------------------------------------------------------------------------
# Protocol (the Adapter interface)
# ---------------------------------------------------------------------------

@runtime_checkable
class HttpTransportAdapter(Protocol):
    """Async HTTP interface used by gateways that opt-in to the adapter pattern."""

    async def post(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None,
        timeout: float,
    ) -> dict[str, Any]: ...

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None,
        headers: dict[str, str] | None,
        timeout: float,
    ) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# HttpxAdapter — production implementation
# ---------------------------------------------------------------------------

class HttpxAdapter:
    """
    httpx-backed transport adapter.

    If `client` is provided it is reused across calls (connection pooling).
    If omitted, a fresh client is created and closed per request.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        retry: RetryStrategy | None = None,
        gateway: str | None = None,
    ) -> None:
        self._client = client
        self._retry: RetryStrategy = retry or NoRetryStrategy()
        self._gateway = gateway

    async def post(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=timeout)
        try:
            async def _call() -> httpx.Response:
                resp = await client.post(url, json=payload, headers=headers or {})
                resp.raise_for_status()
                return resp

            try:
                resp = await self._retry.execute(_call, self._gateway)
            except GatewayConnectionError:
                raise
            except httpx.HTTPError as exc:
                raise GatewayConnectionError(str(exc), gateway=self._gateway) from exc
            return dict(resp.json())
        finally:
            if owned:
                await client.aclose()

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=timeout)
        try:
            async def _call() -> httpx.Response:
                resp = await client.get(url, params=params, headers=headers or {})
                resp.raise_for_status()
                return resp

            try:
                resp = await self._retry.execute(_call, self._gateway)
            except GatewayConnectionError:
                raise
            except httpx.HTTPError as exc:
                raise GatewayConnectionError(str(exc), gateway=self._gateway) from exc
            return dict(resp.json())
        finally:
            if owned:
                await client.aclose()


# ---------------------------------------------------------------------------
# InMemoryAdapter — test double
# ---------------------------------------------------------------------------

class InMemoryAdapter:
    """
    In-memory transport adapter for unit tests.

    Provide a mapping of URL → response dict (or an Exception to simulate
    network/HTTP errors).  Every call is recorded in `self.calls` for
    assertion.

    Example::

        adapter = InMemoryAdapter({
            "https://api.zarinpal.com/pg/v4/payment/request.json": {
                "data": {"code": 100, "authority": "AUTH"},
                "errors": [],
            },
            "https://api.zarinpal.com/pg/v4/payment/verify.json":
                httpx.ConnectError("simulated failure"),
        })
    """

    def __init__(self, responses: dict[str, dict[str, Any] | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def _lookup(self, url: str) -> dict[str, Any]:
        if url not in self.responses:
            raise KeyError(f"InMemoryAdapter: no response configured for URL '{url}'")
        result = self.responses[url]
        if isinstance(result, Exception):
            raise result
        return result

    async def post(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        self.calls.append({"method": "POST", "url": url, "payload": payload, "headers": headers})
        return self._lookup(url)

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        self.calls.append({"method": "GET", "url": url, "params": params, "headers": headers})
        return self._lookup(url)


__all__ = [
    "HttpTransportAdapter",
    "HttpxAdapter",
    "InMemoryAdapter",
]
