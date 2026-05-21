---
name: project-overview
description: Goals, architecture, gateway list, and implementation status for fastapi-iranian-bank-gateways
metadata:
  type: project
---

# fastapi-iranian-bank-gateways — Project Overview

**Goal:** A pip-installable Python package providing FastAPI integration for all major Iranian bank payment gateways. Developers install it and mount routes into their own FastAPI apps.

**Reference implementation:** `/test/agamemnon` — existing FastAPI app with Mellat, Saderat, Pasargad, Saman, Sepah implemented as procedural adapters.

**Why:** The reference app is a standalone service, not reusable. This package lets any developer `pip install` and use Iranian gateways in their own FastAPI project.

## Architecture Decisions

- **AbstractGateway** base class with `initiate()` and `verify()` async methods
- **GatewayManager** registers gateways by slug and produces a FastAPI router
- **No mandatory database** — users provide 3 async callbacks: `get_order_info`, `on_success`, `on_failure`
- **Pydantic v2** models for all request/response types; `frozen=True` configs
- **SOAP is optional** — zeep in `[soap]` extras; lazy import raises `MissingDependencyError` with clear hint
- **httpx** for async HTTP (replaces blocking `requests` from reference)
- **Jinja2** templates for auto-submit HTML forms (Mellat, Saderat, Saman, Parsian)
- **Pasargad two-step verify** (`check_verify` + `verify`) encapsulated inside `PasargadGateway.verify()`
- **Unified routes:** `POST /{gateway}/pay`, `GET|POST /{gateway}/verify`

## Gateway Implementation Status

### Tier 1 — Bank PSPs
- [x] Mellat (به‌پرداخت ملت) — SOAP, form-POST, POST callback
- [x] Saderat (پرداخت الکترونیک صادرات) — REST, form-POST, GET callback
- [x] Pasargad — REST, redirect, GET callback (2-step verify)
- [x] Saman — REST, form-POST, GET callback
- [x] Sepah — SOAP, redirect, POST callback

### Tier 2 — Additional Bank PSPs
- [x] Parsian (پارسیان) — SOAP, form-POST
- [x] Melli/Behpardakht — REST
- [x] Irankish (ایران کیش) — REST
- [x] Tejarat (تجارت) — REST
- [x] Eghtesad Novin (اقتصاد نوین) — REST

### Tier 3 — Fintech Aggregators
- [x] Zarinpal (زرین‌پال) — REST/JSON, redirect, GET callback [IMPLEMENTED & TESTED]
- [x] IDPay (آیدی پی) — REST/JSON, redirect, POST callback [IMPLEMENTED & TESTED]
- [x] NextPay (نکست پی) — REST/JSON, redirect, GET callback
- [x] Zibal (زیبال) — REST/JSON, redirect, GET callback
- [x] PayPing — REST/JSON, redirect, GET callback
- [x] Pay.ir — REST/JSON, redirect, GET callback
- [x] Vandar — REST/JSON, redirect, POST callback

## Test Suite
- 20 tests, 20 passing (pytest)
- Covers: models, exceptions, GatewayManager routing, Zarinpal full flow, IDPay full flow
- HTTP mocked via respx
- Run: `python3 -m pytest tests/ -v`

## Package Structure

```
src/fastapi_iranian_bank_gateways/
├── __init__.py          GatewayManager, models, exceptions re-exported
├── manager.py           GatewayManager + FastAPI router factory
├── base/gateway.py      AbstractGateway ABC
├── base/config.py       BaseGatewayConfig (Pydantic v2, frozen)
├── models/payment.py    PaymentRequest, FormInitiateResponse, RedirectInitiateResponse
├── models/callback.py   BankCallbackData, PaymentResult
├── models/enums.py      PaymentStatus, Currency
├── exceptions/errors.py All custom exceptions
├── utils/soap.py        Lazy zeep import helper
├── utils/form.py        Jinja2 form renderer
├── utils/http.py        httpx async helper
├── templates/           HTML auto-submit form templates
└── gateways/            Per-gateway implementations (tier1, tier2, tier3)
```

## How to Apply

- When adding a new gateway: create `gateways/tier{N}/{name}/` with `gateway.py`, `config.py`, `schemas.py`, `__init__.py`; add to `gateways/__init__.py` re-exports
- When asked about gateway credentials: see `gateway_reference.md`
- Pasargad is the only gateway with a 2-step verify flow
- SOAP gateways require `[soap]` extra: Mellat, Sepah, Parsian
