# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-21

### Added

- **17 Iranian bank payment gateways**: Mellat, Saderat, Pasargad, Saman, Sepah (Tier 1);
  Parsian, Melli, Irankish, Tejarat, Eghtesad Novin (Tier 2); Zarinpal, IDPay, NextPay,
  Zibal, PayPing, Pay.ir, Vandar (Tier 3)
- `GatewayManager` — registers gateways by slug and generates a FastAPI `APIRouter`
  with unified `POST /{gw}/pay`, `GET /{gw}/verify`, `POST /{gw}/verify` routes
- Callback-based design: `get_order_info`, `on_success`, `on_failure` async hooks
  eliminate mandatory database dependency
- Pydantic v2 models for `PaymentRequest`, `PaymentResult`, `BankCallbackData`
- `AbstractGateway` ABC with `initiate()` / `verify()` async interface
- SOAP support via optional `[soap]` extra (zeep + lxml); lazy import raises
  `MissingDependencyError` with install hint if missing
- Jinja2 HTML auto-submit form templates for form-POST gateways (Mellat, Saderat,
  Saman, Parsian)
- Pasargad two-step verify (`CheckTransactionResult` → `VerifyPayment`) encapsulated
  transparently in `PasargadGateway.verify()`
- PayPing Toman conversion (÷10) handled internally
- Configurable `timeout` per gateway (`BaseGatewayConfig.timeout`, default 30s)
- `GatewayManager` async context manager for shared `httpx.AsyncClient` connection
  pooling (use with FastAPI lifespan)
- Retry with exponential backoff in `utils/http.py` (`max_retries`, `retry_backoff`)
- PII-safe structured logging in `GatewayManager` (gateway, order_id, status,
  error_code logged — never card_number, amount, mobile, raw_response)
- X-Request-ID propagation through payment initiate and verify flows
- GitHub Actions CI: lint + type-check + test on Python 3.10/3.11/3.12
- GitHub Actions CD: PyPI Trusted Publisher (OIDC) + GitHub Release on `v*.*.*` tags
- Dependabot: weekly pip + Actions dependency updates
- Pre-commit hooks: ruff (lint + format), mypy, standard file checks
- Makefile: install / test / lint / type-check / format / coverage / build / clean
- 113 tests, 90% coverage (pytest + respx for HTTP mocking, unittest.mock for SOAP)

[Unreleased]: https://github.com/MehranDashti/fastapi-iranian-bank-gateways/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/MehranDashti/fastapi-iranian-bank-gateways/releases/tag/v0.1.0
