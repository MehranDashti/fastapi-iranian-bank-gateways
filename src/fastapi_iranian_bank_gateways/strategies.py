"""
Strategy pattern implementations for fastapi-iranian-bank-gateways.

Two strategy families:

1. **InitiateResponseStrategy** — controls how a gateway's initiate() result is
   converted into a FastAPI HTTP response. Dispatch is keyed on the response's
   `type` discriminator field ("form" or "redirect").

2. **RetryStrategy** — controls how transient HTTP errors are retried.
   The default (NoRetryStrategy) has zero overhead. Use ExponentialBackoffStrategy
   or LinearBackoffStrategy for gateways that require resilience.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

import httpx
from fastapi import Response
from fastapi.responses import HTMLResponse, RedirectResponse

from .exceptions.errors import GatewayConnectionError
from .models.payment import FormInitiateResponse, InitiateResponse, RedirectInitiateResponse

logger = logging.getLogger(__name__)

_RETRYABLE = (httpx.TimeoutException, httpx.NetworkError)


# ---------------------------------------------------------------------------
# InitiateResponseStrategy
# ---------------------------------------------------------------------------

class InitiateResponseStrategy(ABC):
    """Converts an InitiateResponse into a FastAPI Response."""

    @abstractmethod
    def handle(self, result: InitiateResponse) -> Response: ...


class FormInitiateStrategy(InitiateResponseStrategy):
    """Renders an HTML auto-submit form (used by Mellat, Saderat, Saman, Parsian)."""

    def handle(self, result: FormInitiateResponse) -> HTMLResponse:  # type: ignore[override]
        return HTMLResponse(content=result.html)


class RedirectInitiateStrategy(InitiateResponseStrategy):
    """Issues a 302 redirect to the bank's payment page."""

    def handle(self, result: RedirectInitiateResponse) -> RedirectResponse:  # type: ignore[override]
        return RedirectResponse(url=result.url, status_code=302)


#: Module-level registry — extend this dict to support new response types.
INITIATE_STRATEGIES: dict[str, InitiateResponseStrategy] = {
    "form": FormInitiateStrategy(),
    "redirect": RedirectInitiateStrategy(),
}


def handle_initiate_response(result: InitiateResponse) -> Response:
    """Dispatch an InitiateResponse to the appropriate strategy."""
    strategy = INITIATE_STRATEGIES.get(result.type)
    if strategy is None:
        raise ValueError(f"No InitiateResponseStrategy registered for type '{result.type}'")
    return strategy.handle(result)


# ---------------------------------------------------------------------------
# RetryStrategy
# ---------------------------------------------------------------------------

class RetryStrategy(ABC):
    """Controls retry behaviour for transient HTTP failures."""

    @abstractmethod
    async def execute(
        self,
        coro_fn: Callable[[], Awaitable[httpx.Response]],
        gateway: str | None = None,
    ) -> httpx.Response: ...


class NoRetryStrategy(RetryStrategy):
    """Single attempt — raises GatewayConnectionError on any network failure."""

    async def execute(
        self,
        coro_fn: Callable[[], Awaitable[httpx.Response]],
        gateway: str | None = None,
    ) -> httpx.Response:
        try:
            return await coro_fn()
        except _RETRYABLE as exc:
            raise GatewayConnectionError(str(exc), gateway=gateway) from exc


class ExponentialBackoffStrategy(RetryStrategy):
    """Retry up to `max_retries` times with exponential backoff.

    Wait time between attempts: `backoff * 2^attempt` seconds.
    Only retries TimeoutException and NetworkError — never 4xx/5xx.
    """

    def __init__(self, max_retries: int = 3, backoff: float = 1.0) -> None:
        self.max_retries = max_retries
        self.backoff = backoff

    async def execute(
        self,
        coro_fn: Callable[[], Awaitable[httpx.Response]],
        gateway: str | None = None,
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await coro_fn()
            except _RETRYABLE as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait = self.backoff * (2 ** attempt)
                    logger.warning(
                        "Gateway %s: transient error attempt %d/%d, retry in %.1fs: %s",
                        gateway, attempt + 1, self.max_retries + 1, wait, exc,
                    )
                    await asyncio.sleep(wait)
        raise GatewayConnectionError(str(last_exc), gateway=gateway) from last_exc


class LinearBackoffStrategy(RetryStrategy):
    """Retry up to `max_retries` times with a fixed wait between attempts.

    Only retries TimeoutException and NetworkError — never 4xx/5xx.
    """

    def __init__(self, max_retries: int = 3, wait_seconds: float = 2.0) -> None:
        self.max_retries = max_retries
        self.wait_seconds = wait_seconds

    async def execute(
        self,
        coro_fn: Callable[[], Awaitable[httpx.Response]],
        gateway: str | None = None,
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await coro_fn()
            except _RETRYABLE as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    logger.warning(
                        "Gateway %s: transient error attempt %d/%d, retry in %.1fs: %s",
                        gateway, attempt + 1, self.max_retries + 1, self.wait_seconds, exc,
                    )
                    await asyncio.sleep(self.wait_seconds)
        raise GatewayConnectionError(str(last_exc), gateway=gateway) from last_exc


__all__ = [
    "InitiateResponseStrategy",
    "FormInitiateStrategy",
    "RedirectInitiateStrategy",
    "INITIATE_STRATEGIES",
    "handle_initiate_response",
    "RetryStrategy",
    "NoRetryStrategy",
    "ExponentialBackoffStrategy",
    "LinearBackoffStrategy",
]
