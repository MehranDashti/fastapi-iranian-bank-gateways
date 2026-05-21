# fastapi-iranian-bank-gateways

[![Tests](https://github.com/MehranDashti/fastapi-iranian-bank-gateways/actions/workflows/test.yml/badge.svg)](https://github.com/MehranDashti/fastapi-iranian-bank-gateways/actions/workflows/test.yml)
[![PyPI version](https://img.shields.io/pypi/v/fastapi-iranian-bank-gateways.svg)](https://pypi.org/project/fastapi-iranian-bank-gateways/)
[![Python versions](https://img.shields.io/pypi/pyversions/fastapi-iranian-bank-gateways.svg)](https://pypi.org/project/fastapi-iranian-bank-gateways/)
[![Downloads](https://img.shields.io/pypi/dm/fastapi-iranian-bank-gateways.svg)](https://pypi.org/project/fastapi-iranian-bank-gateways/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A pip-installable Python package providing **FastAPI integration for all major Iranian bank payment gateways** (درگاه‌های پرداخت بانکی ایران).

A **toolkit**, not a framework — you own your routes and your business logic. The library handles the bank protocol: initiating payments, parsing callbacks, and verifying transactions.

---

## Table of Contents

- [Features](#features)
- [Supported Gateways](#supported-gateways)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Gateway Configuration](#gateway-configuration)
  - [Tier 1 — Bank PSPs](#tier-1--bank-psps)
  - [Tier 2 — Additional Bank PSPs](#tier-2--additional-bank-psps)
  - [Tier 3 — Fintech Aggregators](#tier-3--fintech-aggregators)
- [PaymentRequest Fields](#paymentrequest-fields)
- [PaymentResult Fields](#paymentresult-fields)
- [GatewayManager](#gatewaymanager)
- [GatewayFactory](#gatewayfactory)
- [Error Handling](#error-handling)
- [Advanced Usage](#advanced-usage)
- [Writing a Custom Gateway](#writing-a-custom-gateway)
- [Testing](#testing)
- [License](#license)

---

## Features

- **17 gateways** — all major Iranian bank PSPs and fintech aggregators
- **Toolkit pattern** — you write your own routes; the library handles bank protocols
- **Fully async** — built on `httpx` and FastAPI async routes throughout
- **SOAP gateways** supported via optional `zeep` dependency
- **Pydantic v2** models for type-safe configs and responses
- **Sandbox/test mode** — `sandbox=True` flag on every config
- **Duplicate payment detection** — `PaymentStatus.DUPLICATE` for idempotent retries
- **Auto-submit HTML forms** — Mellat, Saderat, Saman, Parsian handled transparently
- **`InMemoryAdapter`** for fast, zero-mock unit tests
- **`GatewayFactory`** — create gateways from a config dict or environment variables

---

## Supported Gateways

### Tier 1 — Bank PSPs

| Gateway | Name (FA) | Protocol | Callback |
|---------|-----------|----------|----------|
| `mellat` | به‌پرداخت ملت | SOAP | POST |
| `saderat` | پرداخت الکترونیک صادرات | REST | GET |
| `pasargad` | پاسارگاد | REST | GET |
| `saman` | سامان کیش | REST | GET |
| `sepah` | سپه | SOAP | POST |

### Tier 2 — Additional Bank PSPs

| Gateway | Name (FA) | Protocol | Callback |
|---------|-----------|----------|----------|
| `parsian` | پارسیان | SOAP | POST |
| `melli` | به‌پرداخت ملی | REST | POST |
| `irankish` | ایران کیش | REST | POST |
| `tejarat` | تجارت | REST | POST |
| `eghtesad_novin` | اقتصاد نوین | REST | POST |

### Tier 3 — Fintech Aggregators

| Gateway | Name (FA) | Protocol | Callback |
|---------|-----------|----------|----------|
| `zarinpal` | زرین‌پال | REST/JSON | GET |
| `idpay` | آیدی پی | REST/JSON | POST |
| `zibal` | زیبال | REST/JSON | GET |
| `nextpay` | نکست پی | REST/JSON | GET |
| `pay_ir` | پی‌آی‌آر | REST/JSON | GET |
| `payping` | پی‌پینگ | REST/JSON | GET |
| `vandar` | وندار | REST/JSON | POST |

> **SOAP gateways** (Mellat, Sepah, Parsian) require the `[soap]` extra — see [Installation](#installation).

---

## Installation

```bash
# REST-only gateways
pip install fastapi-iranian-bank-gateways

# With SOAP support — adds zeep for Mellat, Sepah, Parsian
pip install "fastapi-iranian-bank-gateways[soap]"

# All extras
pip install "fastapi-iranian-bank-gateways[all]"
```

**Requirements:** Python 3.10+, FastAPI ≥ 0.100, Pydantic v2

---

## Quick Start

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi_iranian_bank_gateways import (
    GatewayFactory, GatewayManager, PaymentRequest, PaymentStatus,
)
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

# --- 1. Configure gateways ---
# From env vars:  GATEWAY_ZARINPAL_MERCHANT_ID=...  GATEWAY_ZARINPAL_SANDBOX=true
manager = GatewayManager(gateways=GatewayFactory.from_env("GATEWAY_"))

# Or explicitly:
# manager = GatewayManager(gateways=[
#     GatewayFactory.create("zarinpal", {"merchant_id": "...", "sandbox": True}),
# ])


# --- 2. Open a shared connection pool in FastAPI lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with manager:
        yield

app = FastAPI(lifespan=lifespan)


# --- 3. Initiate a payment — developer's own route ---
@app.post("/pay/{gateway_slug}")
async def initiate_payment(gateway_slug: str, req: PaymentRequest):
    gw = manager.get(gateway_slug)
    result = await gw.initiate(req)
    # Returns 302 RedirectResponse or 200 HTMLResponse (auto-submit form)
    return handle_initiate_response(result)


# --- 4. Handle bank callback — developer's own route ---
@app.get("/callback/{gateway_slug}")   # GET for most gateways
async def payment_callback(gateway_slug: str, request: Request):
    gw = manager.get(gateway_slug)

    # For gateways that don't send amount/order_id in the callback (e.g. Zarinpal),
    # fetch them from your database and pass explicitly:
    order = await db.get_order_by_authority(request.query_params.get("Authority"))
    result = await gw.verify(
        gw.parse_callback(
            dict(request.query_params),
            amount=order.amount,      # Rials, from your DB
            order_id=order.id,        # from your DB
        )
    )

    if result.status in (PaymentStatus.SUCCESS, PaymentStatus.DUPLICATE):
        await db.mark_order_paid(result.order_id, ref=result.reference_id)
        return RedirectResponse(f"/success?ref={result.reference_id}")
    return RedirectResponse(f"/failure?order={result.order_id}&code={result.error_code}")


# --- 5. POST callback (for Mellat, IDPay, Melli, etc.) ---
@app.post("/callback/{gateway_slug}")
async def payment_callback_post(gateway_slug: str, request: Request):
    gw = manager.get(gateway_slug)
    form = await request.form()

    # Most POST-callback gateways include order_id in the form data
    order = await db.get_order(form.get("orderId") or form.get("order_id"))
    result = await gw.verify(
        gw.parse_callback(dict(form), amount=order.amount, order_id=order.id)
    )

    if result.status in (PaymentStatus.SUCCESS, PaymentStatus.DUPLICATE):
        await db.mark_order_paid(result.order_id, ref=result.reference_id)
        return RedirectResponse(f"/success?ref={result.reference_id}")
    return RedirectResponse(f"/failure?order={result.order_id}")
```

---

## How It Works

### Payment Flow

```
Your frontend              Your FastAPI app               Bank
     │                           │                          │
     │  POST /pay/zarinpal       │                          │
     │  { order_id, amount,      │                          │
     │    callback_url }         │                          │
     │ ──────────────────────►  │                          │
     │                           │  POST to bank API        │
     │                           │ ──────────────────────► │
     │                           │  ◄── authority token ── │
     │  302 → bank payment page  │                          │
     │ ◄─────────────────────── │                          │
     │ ────────────────────────────────────────────────────►│
     │               (user fills card details on bank page) │
     │                           │  GET /callback/zarinpal  │
     │                           │  ?Authority=...&Status=OK│
     │                           │ ◄──────────────────────── │
     │                           │  (look up order from DB) │
     │                           │  POST verify to bank     │
     │                           │ ──────────────────────► │
     │                           │  ◄── confirmed ─────── │
     │                           │  mark order as paid      │
     │  302 → your success page  │                          │
     │ ◄─────────────────────── │                          │
```

### The Two Gateway Methods

Every gateway exposes exactly two async methods:

```python
# Step 1: start a payment — returns a redirect URL or HTML auto-submit form
result: InitiateResponse = await gateway.initiate(PaymentRequest(
    order_id="ORDER-001",
    amount=100000,           # Rials
    callback_url="https://myapp.com/callback/zarinpal",
    description="Purchase",  # optional
    mobile="09123456789",    # optional
))

# Step 2: verify after bank redirects back
result: PaymentResult = await gateway.verify(
    gateway.parse_callback(
        dict(request.query_params),  # or dict(await request.form())
        amount=100000,   # from your DB (required by Zarinpal and PayPing)
        order_id="ORDER-001",  # from your DB
    )
)
```

### `parse_callback()` and the `amount` parameter

Some gateways (Zarinpal, PayPing) **require the order amount** when calling the bank's verify API. Since these gateways don't return the amount in their callback, you must fetch it from your own database and pass it explicitly:

```python
# Zarinpal callback only contains: Authority, Status
authority = request.query_params.get("Authority")
order = await db.get_order_by_authority(authority)

result = await gw.verify(
    gw.parse_callback(
        dict(request.query_params),
        amount=order.amount,    # REQUIRED for Zarinpal and PayPing
        order_id=order.id,
    )
)
```

Most other gateways (IDPay, Zibal, Mellat, etc.) include all necessary data in their callback params and do not require `amount` to be passed.

### Initiate Response Types

- **`RedirectInitiateResponse`** — most gateways: redirect the user to `result.url`
- **`FormInitiateResponse`** — Mellat, Saderat, Saman, Parsian: return `result.html` which auto-submits to the bank

`handle_initiate_response(result)` handles both cases automatically.

---

## Gateway Configuration

All configs extend `BaseGatewayConfig` which provides:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sandbox` | `bool` | `False` | Use sandbox/test endpoints |

### Tier 1 — Bank PSPs

#### Mellat (به‌پرداخت ملت)

```python
from fastapi_iranian_bank_gateways.gateways.tier1.mellat import MellatConfig, MellatGateway

MellatConfig(
    terminal_id=12345678,       # int — terminal ID from bank
    username="terminal_user",   # str — terminal username
    password="terminal_pass",   # str — terminal password
    sandbox=False,
)
```

> Requires `pip install "fastapi-iranian-bank-gateways[soap]"`

---

#### Saderat (پرداخت الکترونیک صادرات)

```python
from fastapi_iranian_bank_gateways.gateways.tier1.saderat import SaderatConfig, SaderatGateway

SaderatConfig(
    terminal_id="your_terminal_id",  # str — terminal ID from bank
)
```

---

#### Pasargad (پاسارگاد)

```python
from fastapi_iranian_bank_gateways.gateways.tier1.pasargad import PasargadConfig, PasargadGateway

PasargadConfig(
    username="pep_username",       # str — PEP panel username
    password="pep_password",       # str — PEP panel password
    terminal_number="TERM123",     # str — terminal number
    merchant_code="MERCH456",      # str — merchant code
)
```

Pasargad uses a **two-step verify** (`check_verify` then `verify`) handled transparently inside the library.

---

#### Saman (سامان کیش)

```python
from fastapi_iranian_bank_gateways.gateways.tier1.saman import SamanConfig, SamanGateway

SamanConfig(
    terminal_id="your_terminal_id",  # str — terminal ID
    password="your_password",        # str — terminal password
)
```

---

#### Sepah (سپه)

```python
from fastapi_iranian_bank_gateways.gateways.tier1.sepah import SepahConfig, SepahGateway

SepahConfig(
    login_account="your_login_account",  # str — login account from bank
)
```

> Requires `pip install "fastapi-iranian-bank-gateways[soap]"`

---

### Tier 2 — Additional Bank PSPs

#### Parsian (پارسیان)

```python
from fastapi_iranian_bank_gateways.gateways.tier2.parsian import ParsianConfig, ParsianGateway

ParsianConfig(
    login_account="your_login_account",  # str — login account from bank
)
```

> Requires `pip install "fastapi-iranian-bank-gateways[soap]"`

---

#### Melli / Behpardakht (به‌پرداخت ملی)

```python
from fastapi_iranian_bank_gateways.gateways.tier2.melli import MelliConfig, MelliGateway

MelliConfig(
    terminal_id="your_terminal_id",  # str
    merchant_id="your_merchant_id",  # str
    sandbox=False,
)
```

---

#### Irankish (ایران کیش)

```python
from fastapi_iranian_bank_gateways.gateways.tier2.irankish import IrankishConfig, IrankishGateway

IrankishConfig(
    terminal_id="your_terminal_id",   # str
    acceptor_id="your_acceptor_id",   # str
    pass_phrase="your_pass_phrase",   # str
)
```

---

#### Tejarat (تجارت)

```python
from fastapi_iranian_bank_gateways.gateways.tier2.tejarat import TejaratConfig, TejaratGateway

TejaratConfig(
    terminal_id="your_terminal_id",  # str
)
```

---

#### Eghtesad Novin (اقتصاد نوین)

```python
from fastapi_iranian_bank_gateways.gateways.tier2.eghtesad_novin import (
    EghtesadNovinConfig, EghtesadNovinGateway,
)

EghtesadNovinConfig(
    username="ipg_username",     # str
    password="ipg_password",     # str
    merchant_id="merchant_id",   # str
)
```

---

### Tier 3 — Fintech Aggregators

#### Zarinpal (زرین‌پال) — most popular

```python
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig, ZarinpalGateway

ZarinpalConfig(
    merchant_id="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # str — 36-char UUID from dashboard
    sandbox=True,   # uses sandbox.zarinpal.com
)
```

> **Note:** Zarinpal's verify API requires the order amount. Pass it to `parse_callback(amount=...)`.

Sandbox merchant ID for testing: any 36-character string (e.g. `"00000000-0000-0000-0000-000000000000"`).

---

#### IDPay (آیدی پی)

```python
from fastapi_iranian_bank_gateways.gateways.tier3.idpay import IDPayConfig, IDPayGateway

IDPayConfig(
    api_key="your-api-key",  # str — from IDPay dashboard
    sandbox=True,            # adds X-SANDBOX: 1 header
)
```

---

#### Zibal (زیبال)

```python
from fastapi_iranian_bank_gateways.gateways.tier3.zibal import ZibalConfig, ZibalGateway

ZibalConfig(
    merchant="your_merchant_code",  # str — use "zibal" for sandbox testing
)
```

---

#### NextPay (نکست پی)

```python
from fastapi_iranian_bank_gateways.gateways.tier3.nextpay import NextPayConfig, NextPayGateway

NextPayConfig(
    api_key="your_api_key",  # str — from NextPay dashboard
)
```

---

#### Pay.ir

```python
from fastapi_iranian_bank_gateways.gateways.tier3.pay_ir import PayIrConfig, PayIrGateway

PayIrConfig(
    api="your_api_key",   # str — from Pay.ir dashboard
                          # use "test" for sandbox mode
)
```

---

#### PayPing

```python
from fastapi_iranian_bank_gateways.gateways.tier3.payping import PayPingConfig, PayPingGateway

PayPingConfig(
    access_token="your_bearer_token",  # str — from PayPing dashboard
)
```

> Note: PayPing amounts are in **Tomans** (IRR ÷ 10). The library converts automatically.  
> **Note:** PayPing's verify API requires the order amount. Pass it to `parse_callback(amount=...)`.

---

#### Vandar

```python
from fastapi_iranian_bank_gateways.gateways.tier3.vandar import VandarConfig, VandarGateway

VandarConfig(
    api_key="your_api_key",  # str — from Vandar dashboard
)
```

---

## PaymentRequest Fields

```python
PaymentRequest(
    order_id="ORDER-001",                    # str   — your unique order identifier
    amount=100000,                           # int   — amount in Rials (IRR), must be > 0
    callback_url="https://myapp.com/cb/zp",  # str   — full URL the bank redirects back to
    currency=Currency.IRR,                   # enum  — "IRR" (default)
    mobile="09123456789",                    # str   — payer mobile (optional, pre-fills bank form)
    email="user@example.com",               # str   — payer email (optional)
    description="Order #001",               # str   — shown on bank payment page (optional)
    metadata={},                            # dict  — passed through; not sent to bank
)
```

> All amounts are in **Rials (IRR)**. For example, 10,000 Tomans = 100,000 Rials.

---

## PaymentResult Fields

Returned by `gateway.verify()`.

| Field | Type | Description |
|-------|------|-------------|
| `status` | `PaymentStatus` | `SUCCESS`, `FAILED`, `CANCELLED`, `PENDING`, `DUPLICATE` |
| `gateway_slug` | `str` | e.g. `"zarinpal"`, `"mellat"` |
| `order_id` | `str` | Your order identifier |
| `transaction_id` | `str \| None` | Gateway's internal transaction ID |
| `reference_id` | `str \| None` | Bank reference number (RRN/RefNum/ref_id) |
| `amount` | `int \| None` | Confirmed amount in Rials |
| `card_number` | `str \| None` | Masked card number (if provided by bank) |
| `error_code` | `str \| None` | Bank error code on failure |
| `error_message` | `str \| None` | Human-readable error description |
| `raw_response` | `dict` | Full raw response from the bank (for logging) |

### PaymentStatus Values

| Status | Meaning |
|--------|---------|
| `SUCCESS` | Payment verified and captured successfully |
| `FAILED` | Bank rejected or verification failed |
| `CANCELLED` | User cancelled or returned without paying |
| `PENDING` | Payment initiated but not yet confirmed |
| `DUPLICATE` | Payment was already verified — treat as success |

---

## GatewayManager

`GatewayManager` is a **registry + connection pool**. It holds your configured gateways and lets you look them up by slug in request handlers.

```python
from fastapi_iranian_bank_gateways import GatewayManager

manager = GatewayManager(gateways=[
    ZarinpalGateway(ZarinpalConfig(merchant_id="...", sandbox=True)),
    IDPayGateway(IDPayConfig(api_key="...", sandbox=True)),
    MellatGateway(MellatConfig(terminal_id=123, username="u", password="p")),
])

# Look up a gateway in a request handler
gw = manager.get("zarinpal")   # raises GatewayConfigurationError if not registered
gw = manager["zarinpal"]       # same, using [] syntax

# Check if a gateway is registered
if "zarinpal" in manager:
    ...

# List registered slugs
manager.slugs()  # ["zarinpal", "idpay", "mellat"]
```

### Shared Connection Pool (recommended for production)

Use `GatewayManager` as an async context manager in the FastAPI lifespan to share one `httpx.AsyncClient` across all requests:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with manager:   # opens shared HTTP client
        yield             # closes on shutdown

app = FastAPI(lifespan=lifespan)
```

---

## GatewayFactory

`GatewayFactory` creates gateway instances from a slug + config, without manual imports.

### Create one gateway

```python
from fastapi_iranian_bank_gateways import GatewayFactory

gw = GatewayFactory.create("zarinpal", {
    "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "sandbox": True,
})
```

### Create multiple gateways

```python
gateways = GatewayFactory.create_all({
    "zarinpal": {"merchant_id": "...", "sandbox": True},
    "mellat":   {"terminal_id": 12345678, "username": "u", "password": "p"},
    "idpay":    {"api_key": "...", "sandbox": True},
})
manager = GatewayManager(gateways=gateways)
```

### Auto-discover from environment variables

```bash
# .env
GATEWAY_ZARINPAL_MERCHANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
GATEWAY_ZARINPAL_SANDBOX=true
GATEWAY_IDPAY_API_KEY=your-api-key
GATEWAY_IDPAY_SANDBOX=true
```

```python
gateways = GatewayFactory.from_env("GATEWAY_")
manager = GatewayManager(gateways=gateways)
```

Convention: `{PREFIX}{SLUG_UPPER}_{FIELD_UPPER}=value`

### List available slugs

```python
GatewayFactory.available_slugs()
# ['eghtesad_novin', 'idpay', 'irankish', 'mellat', 'melli',
#  'nextpay', 'parsian', 'pasargad', 'pay_ir', 'payping',
#  'saderat', 'saman', 'sepah', 'tejarat', 'vandar', 'zarinpal', 'zibal']
```

---

## Error Handling

All exceptions inherit from `GatewayError`.

```python
from fastapi_iranian_bank_gateways import (
    GatewayError,              # base class
    GatewayConfigurationError, # bad config or unknown gateway slug
    GatewayConnectionError,    # network failure talking to bank
    GatewayAuthError,          # token/auth request failed
    GatewayPaymentError,       # bank rejected the payment
    MissingDependencyError,    # zeep not installed for a SOAP gateway
    DuplicatePaymentError,     # already verified (subclass of GatewayPaymentError)
)
```

Every exception exposes:
- `.gateway` — gateway slug where the error occurred
- `.code` — bank error code string (when available)
- `.raw` — raw bank response dict (on `GatewayPaymentError`)

### Handling errors in your routes

```python
from fastapi import HTTPException
from fastapi_iranian_bank_gateways import GatewayConfigurationError, GatewayConnectionError

@app.post("/pay/{gateway_slug}")
async def pay(gateway_slug: str, req: PaymentRequest):
    try:
        gw = manager.get(gateway_slug)
    except GatewayConfigurationError:
        raise HTTPException(status_code=404, detail="Gateway not found")

    try:
        result = await gw.initiate(req)
    except GatewayConnectionError as e:
        raise HTTPException(status_code=503, detail="Bank unreachable")

    return handle_initiate_response(result)
```

### Handling SOAP missing dependency

```python
from fastapi_iranian_bank_gateways import MissingDependencyError

try:
    await mellat_gateway.initiate(request)
except MissingDependencyError as e:
    print(e)
    # → zeep is required for SOAP-based gateways (Mellat, Sepah, Parsian).
    #   Install it with: pip install "fastapi-iranian-bank-gateways[soap]"
```

---

## Advanced Usage

### Loading config from `.env` with pydantic-settings

```python
from pydantic_settings import BaseSettings
from fastapi_iranian_bank_gateways import GatewayFactory, GatewayManager

class Settings(BaseSettings):
    zarinpal_merchant_id: str
    zarinpal_sandbox: bool = False
    idpay_api_key: str = ""

    model_config = {"env_file": ".env"}

settings = Settings()

manager = GatewayManager(gateways=GatewayFactory.create_all({
    "zarinpal": {
        "merchant_id": settings.zarinpal_merchant_id,
        "sandbox": settings.zarinpal_sandbox,
    },
}))
```

### Supporting both GET and POST callbacks

Some gateways use GET (Zarinpal, Zibal, Pay.ir, PayPing, NextPay, Saderat, Saman, Pasargad), others use POST (Mellat, Melli, IDPay, Irankish, Tejarat, Eghtesad Novin, Sepah, Parsian, Vandar).

```python
async def _handle_callback(gateway_slug: str, request: Request, amount: int, order_id: str):
    gw = manager.get(gateway_slug)
    if request.method == "POST":
        form = await request.form()
        params = dict(form)
    else:
        params = dict(request.query_params)
    result = await gw.verify(gw.parse_callback(params, amount=amount, order_id=order_id))
    return result

@app.get("/callback/{gateway_slug}")
async def cb_get(gateway_slug: str, request: Request):
    order = await db.get_order(...)
    result = await _handle_callback(gateway_slug, request, order.amount, order.id)
    ...

@app.post("/callback/{gateway_slug}")
async def cb_post(gateway_slug: str, request: Request):
    order = await db.get_order(...)
    result = await _handle_callback(gateway_slug, request, order.amount, order.id)
    ...
```

### Storing the payment token for later lookup

When you call `gw.initiate()`, the response contains the authority/token from the bank. Store it with the order so you can look it up during the callback:

```python
@app.post("/pay/{gateway_slug}")
async def pay(gateway_slug: str, req: PaymentRequest):
    gw = manager.get(gateway_slug)
    result = await gw.initiate(req)

    if isinstance(result, RedirectInitiateResponse):
        # Extract the authority token from the URL (Zarinpal-style)
        authority = result.url.split("/")[-1]
        await db.save_authority(req.order_id, authority)

    return handle_initiate_response(result)

@app.get("/callback/zarinpal")
async def callback_zarinpal(Authority: str, Status: str):
    order = await db.get_order_by_authority(Authority)
    gw = manager.get("zarinpal")
    result = await gw.verify(
        gw.parse_callback(
            {"Authority": Authority, "Status": Status},
            amount=order.amount,
            order_id=order.id,
        )
    )
    ...
```

---

## Writing a Custom Gateway

Subclass `AbstractGateway` to add a gateway not included in this package:

```python
from typing import ClassVar
from fastapi_iranian_bank_gateways.base.gateway import AbstractGateway
from fastapi_iranian_bank_gateways.base.config import BaseGatewayConfig
from fastapi_iranian_bank_gateways.models.payment import (
    PaymentRequest, InitiateResponse, RedirectInitiateResponse,
)
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData, PaymentResult
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
import httpx


class MyBankConfig(BaseGatewayConfig):
    api_key: str
    # sandbox: bool inherited from BaseGatewayConfig


class MyBankGateway(AbstractGateway):
    gateway_slug: ClassVar[str] = "mybank"
    config_class: ClassVar[type] = MyBankConfig
    callback_method: ClassVar[str] = "GET"   # or "POST"

    def __init__(self, config: MyBankConfig) -> None:
        super().__init__(config)
        self.config: MyBankConfig = config

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://mybank.com/api/pay", json={
                "api_key": self.config.api_key,
                "amount": request.amount,
                "callback": request.callback_url,
                "ref": request.order_id,
            })
        data = resp.json()
        return RedirectInitiateResponse(url=data["redirect_url"])

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        raw = callback_data.raw
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://mybank.com/api/verify", json={
                "api_key": self.config.api_key,
                "token": raw.get("token"),
                "amount": callback_data.amount or 0,
            })
        data = resp.json()
        return PaymentResult(
            status=PaymentStatus.SUCCESS if data["ok"] else PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=str(callback_data.order_id or raw.get("ref", "")),
            reference_id=data.get("rrn"),
            raw_response=data,
        )


# Use it like any built-in gateway
manager = GatewayManager(gateways=[
    MyBankGateway(MyBankConfig(api_key="...", sandbox=False)),
])
```

---

## Testing

### Sandbox mode

Every gateway config accepts `sandbox=True` to point to test/sandbox endpoints:

```python
ZarinpalConfig(merchant_id="...", sandbox=True)   # → sandbox.zarinpal.com
IDPayConfig(api_key="...", sandbox=True)           # → adds X-SANDBOX: 1 header
MellatConfig(..., sandbox=True)                    # → bpms.bpi.ir WSDL
ZibalConfig(merchant="zibal")                      # use literal "zibal" for sandbox
PayIrConfig(api="test")                            # use literal "test" as api key
```

### Unit testing with InMemoryAdapter

`InMemoryAdapter` is a zero-dependency test double that replaces real HTTP calls. No `respx` needed:

```python
import pytest
from fastapi_iranian_bank_gateways.adapters import InMemoryAdapter
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig, ZarinpalGateway
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus

REQUEST_URL = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
VERIFY_URL = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"


@pytest.mark.asyncio
async def test_zarinpal_initiate():
    transport = InMemoryAdapter(responses={
        REQUEST_URL: {
            "data": {"code": 100, "authority": "A000000000000000000000001234567890"},
            "errors": [],
        },
    })
    gateway = ZarinpalGateway(
        ZarinpalConfig(merchant_id="test-id", sandbox=True),
        transport=transport,
    )
    result = await gateway.initiate(PaymentRequest(
        order_id="TEST-001",
        amount=100000,
        callback_url="https://shop.com/callback/zarinpal",
    ))
    assert result.type == "redirect"
    assert "A000000000000000000000001234567890" in result.url


@pytest.mark.asyncio
async def test_zarinpal_verify_success():
    transport = InMemoryAdapter(responses={
        VERIFY_URL: {
            "data": {"code": 100, "ref_id": 987654, "card_pan": "6037****1234"},
            "errors": [],
        },
    })
    gateway = ZarinpalGateway(
        ZarinpalConfig(merchant_id="test-id", sandbox=True),
        transport=transport,
    )
    result = await gateway.verify(
        gateway.parse_callback(
            {"Authority": "A000000000000000000000001234567890", "Status": "OK"},
            amount=100000,
            order_id="TEST-001",
        )
    )
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "987654"
```

### Integration testing with TestClient

```python
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from fastapi_iranian_bank_gateways import GatewayManager, PaymentRequest, PaymentStatus
from fastapi_iranian_bank_gateways.adapters import InMemoryAdapter
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig, ZarinpalGateway
from fastapi_iranian_bank_gateways.strategies import handle_initiate_response

REQUEST_URL = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
VERIFY_URL = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"


@pytest.fixture
def client():
    transport = InMemoryAdapter(responses={
        REQUEST_URL: {"data": {"code": 100, "authority": "TESTAUTH"}, "errors": []},
        VERIFY_URL: {"data": {"code": 100, "ref_id": 123456}, "errors": []},
    })
    gw = ZarinpalGateway(ZarinpalConfig(merchant_id="test-id", sandbox=True), transport=transport)
    manager = GatewayManager(gateways=[gw])
    app = FastAPI()

    @app.post("/pay/{gw_slug}")
    async def pay(gw_slug: str, req: PaymentRequest):
        return handle_initiate_response(await manager.get(gw_slug).initiate(req))

    @app.get("/callback/{gw_slug}")
    async def callback(gw_slug: str, request: Request):
        gateway = manager.get(gw_slug)
        result = await gateway.verify(
            gateway.parse_callback(dict(request.query_params), amount=100000, order_id="O-001")
        )
        if result.status == PaymentStatus.SUCCESS:
            return RedirectResponse(f"/success?ref={result.reference_id}", status_code=302)
        return RedirectResponse("/failure", status_code=302)

    return TestClient(app, follow_redirects=False)


def test_full_flow(client):
    resp = client.post("/pay/zarinpal", json={
        "order_id": "O-001", "amount": 100000,
        "callback_url": "https://myapp.com/callback/zarinpal",
    })
    assert resp.status_code == 302
    assert "TESTAUTH" in resp.headers["location"]

    resp = client.get("/callback/zarinpal", params={"Authority": "TESTAUTH", "Status": "OK"})
    assert resp.status_code == 302
    assert "success" in resp.headers["location"]
```

---

## Project Structure

```
src/fastapi_iranian_bank_gateways/
├── __init__.py           Public API: GatewayManager, GatewayFactory, models, strategies
├── manager.py            GatewayManager (registry + connection pool)
├── factory.py            GatewayFactory (slug-based creation, from_env)
├── strategies.py         handle_initiate_response, RetryStrategy variants
├── adapters.py           HttpxAdapter (production), InMemoryAdapter (testing)
├── base/
│   ├── gateway.py        AbstractGateway ABC
│   └── config.py         BaseGatewayConfig (Pydantic v2, frozen)
├── models/
│   ├── payment.py        PaymentRequest, InitiateResponse types
│   ├── callback.py       BankCallbackData, PaymentResult
│   └── enums.py          PaymentStatus, Currency, GatewayType
├── exceptions/
│   └── errors.py         All custom exceptions
├── utils/
│   ├── http.py           httpx async helpers
│   ├── soap.py           Lazy zeep import with clear error
│   └── form.py           Jinja2 auto-submit form renderer
├── templates/
│   └── generic_form.html Reusable auto-submit HTML form (RTL/Persian)
└── gateways/
    ├── tier1/            Mellat, Saderat, Pasargad, Saman, Sepah
    ├── tier2/            Parsian, Melli, Irankish, Tejarat, EghtesadNovin
    └── tier3/            Zarinpal, IDPay, Zibal, NextPay, PayIr, PayPing, Vandar
```

---

## License

MIT License — see [LICENSE](LICENSE).

---

## Contributing

Pull requests are welcome. To add a new gateway:

1. Create `src/fastapi_iranian_bank_gateways/gateways/tier{N}/{name}/` with `gateway.py`, `config.py`, `__init__.py`
2. Subclass `AbstractGateway` and `BaseGatewayConfig`
3. Add the gateway to `gateways/__init__.py`
4. Add tests in `tests/unit/test_{name}.py`
5. Document the config fields in this README
