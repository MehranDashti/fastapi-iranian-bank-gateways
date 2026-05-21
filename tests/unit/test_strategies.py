"""Tests for InitiateResponseStrategy and RetryStrategy implementations."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.responses import HTMLResponse, RedirectResponse

from fastapi_iranian_bank_gateways.exceptions import GatewayConnectionError
from fastapi_iranian_bank_gateways.models.payment import (
    FormInitiateResponse,
    RedirectInitiateResponse,
)
from fastapi_iranian_bank_gateways.strategies import (
    INITIATE_STRATEGIES,
    ExponentialBackoffStrategy,
    FormInitiateStrategy,
    LinearBackoffStrategy,
    NoRetryStrategy,
    RedirectInitiateStrategy,
    handle_initiate_response,
)

# ---------------------------------------------------------------------------
# InitiateResponseStrategy tests
# ---------------------------------------------------------------------------

def test_form_strategy_returns_html_response():
    strategy = FormInitiateStrategy()
    result = FormInitiateResponse(html="<form>test</form>")
    response = strategy.handle(result)
    assert isinstance(response, HTMLResponse)
    assert response.body == b"<form>test</form>"


def test_redirect_strategy_returns_redirect_response():
    strategy = RedirectInitiateStrategy()
    result = RedirectInitiateResponse(url="https://bank.com/pay?token=abc")
    response = strategy.handle(result)
    assert isinstance(response, RedirectResponse)
    assert response.headers["location"] == "https://bank.com/pay?token=abc"
    assert response.status_code == 302


def test_handle_initiate_response_dispatches_form():
    result = FormInitiateResponse(html="<form/>")
    response = handle_initiate_response(result)
    assert isinstance(response, HTMLResponse)


def test_handle_initiate_response_dispatches_redirect():
    result = RedirectInitiateResponse(url="https://pay.example.com")
    response = handle_initiate_response(result)
    assert isinstance(response, RedirectResponse)


def test_initiate_strategies_registry_has_both_types():
    assert "form" in INITIATE_STRATEGIES
    assert "redirect" in INITIATE_STRATEGIES


def test_handle_initiate_response_unknown_type_raises():
    from fastapi_iranian_bank_gateways.strategies import handle_initiate_response
    # Manually create a fake response with unknown type
    class FakeResponse:
        type = "qrcode"
    with pytest.raises((ValueError, KeyError)):
        handle_initiate_response(FakeResponse())  # type: ignore


# ---------------------------------------------------------------------------
# RetryStrategy tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_retry_succeeds_on_first_call():
    strategy = NoRetryStrategy()
    mock_response = AsyncMock(return_value=httpx.Response(200))
    result = await strategy.execute(mock_response, "test")
    assert result.status_code == 200
    mock_response.assert_called_once()


@pytest.mark.asyncio
async def test_no_retry_raises_on_timeout():
    strategy = NoRetryStrategy()

    async def fail():
        raise httpx.TimeoutException("timeout")

    with pytest.raises(GatewayConnectionError):
        await strategy.execute(fail, "test")


@pytest.mark.asyncio
async def test_exponential_backoff_retries_on_timeout():
    strategy = ExponentialBackoffStrategy(max_retries=2, backoff=0.01)
    call_count = 0

    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.TimeoutException("timeout")
        return httpx.Response(200)

    with patch("fastapi_iranian_bank_gateways.strategies.asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute(flaky, "test")

    assert result.status_code == 200
    assert call_count == 3


@pytest.mark.asyncio
async def test_exponential_backoff_exhausts_retries():
    strategy = ExponentialBackoffStrategy(max_retries=2, backoff=0.01)

    async def always_fail():
        raise httpx.TimeoutException("timeout")

    with patch("fastapi_iranian_bank_gateways.strategies.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(GatewayConnectionError):
            await strategy.execute(always_fail, "test")


@pytest.mark.asyncio
async def test_exponential_backoff_does_not_retry_http_status_error():
    strategy = ExponentialBackoffStrategy(max_retries=3, backoff=0.01)
    call_count = 0

    async def fail_with_status():
        nonlocal call_count
        call_count += 1
        # HTTPStatusError is NOT a NetworkError — should not be retried
        raise httpx.HTTPStatusError(
            "404",
            request=httpx.Request("POST", "http://x"),
            response=httpx.Response(404),
        )

    # HTTPStatusError is not in _RETRYABLE, so it bubbles up on first call
    with pytest.raises(httpx.HTTPStatusError):
        await strategy.execute(fail_with_status, "test")
    assert call_count == 1


@pytest.mark.asyncio
async def test_linear_backoff_retries_on_network_error():
    strategy = LinearBackoffStrategy(max_retries=2, wait_seconds=0.01)
    call_count = 0

    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise httpx.ConnectError("refused")
        return httpx.Response(200)

    with patch("fastapi_iranian_bank_gateways.strategies.asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute(flaky, "test")

    assert result.status_code == 200
    assert call_count == 2


@pytest.mark.asyncio
async def test_linear_backoff_exhausts_retries():
    strategy = LinearBackoffStrategy(max_retries=1, wait_seconds=0.01)

    async def always_fail():
        raise httpx.ConnectError("refused")

    with patch("fastapi_iranian_bank_gateways.strategies.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(GatewayConnectionError):
            await strategy.execute(always_fail, "test")
