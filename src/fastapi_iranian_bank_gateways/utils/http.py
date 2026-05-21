from __future__ import annotations

import logging
from typing import Any

import httpx

from ..exceptions.errors import GatewayConnectionError
from ..strategies import ExponentialBackoffStrategy, NoRetryStrategy, RetryStrategy

logger = logging.getLogger(__name__)

_RETRYABLE = (httpx.TimeoutException, httpx.NetworkError)


async def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    gateway: str | None = None,
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
    # Legacy params — kept for backward compatibility
    max_retries: int = 0,
    retry_backoff: float = 1.0,
    # New: explicit RetryStrategy (takes precedence over max_retries/retry_backoff)
    retry: RetryStrategy | None = None,
) -> dict[str, Any]:
    """POST JSON and return parsed response dict. Raises GatewayConnectionError on network error."""
    _retry = _resolve_retry(retry, max_retries, retry_backoff)
    owned = client is None
    _client = client or httpx.AsyncClient(timeout=timeout)

    async def _call() -> httpx.Response:
        resp = await _client.post(url, json=payload, headers=headers or {})
        resp.raise_for_status()
        return resp

    try:
        try:
            resp = await _retry.execute(_call, gateway)
        except GatewayConnectionError:
            raise
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=gateway) from exc
        return dict(resp.json())
    except GatewayConnectionError:
        raise
    except httpx.HTTPError as exc:
        raise GatewayConnectionError(str(exc), gateway=gateway) from exc
    finally:
        if owned:
            await _client.aclose()


async def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    gateway: str | None = None,
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
    max_retries: int = 0,
    retry_backoff: float = 1.0,
    retry: RetryStrategy | None = None,
) -> dict[str, Any]:
    """GET with optional query params and return parsed response dict."""
    _retry = _resolve_retry(retry, max_retries, retry_backoff)
    owned = client is None
    _client = client or httpx.AsyncClient(timeout=timeout)

    async def _call() -> httpx.Response:
        resp = await _client.get(url, params=params, headers=headers or {})
        resp.raise_for_status()
        return resp

    try:
        try:
            resp = await _retry.execute(_call, gateway)
        except GatewayConnectionError:
            raise
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=gateway) from exc
        return dict(resp.json())
    except GatewayConnectionError:
        raise
    except httpx.HTTPError as exc:
        raise GatewayConnectionError(str(exc), gateway=gateway) from exc
    finally:
        if owned:
            await _client.aclose()


def _resolve_retry(
    retry: RetryStrategy | None,
    max_retries: int,
    retry_backoff: float,
) -> RetryStrategy:
    """Resolve the active RetryStrategy from explicit or legacy params."""
    if retry is not None:
        return retry
    if max_retries > 0:
        return ExponentialBackoffStrategy(max_retries=max_retries, backoff=retry_backoff)
    return NoRetryStrategy()
