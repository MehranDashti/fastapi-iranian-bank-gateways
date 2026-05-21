# fastapi-iranian-bank-gateways

A pip-installable Python package providing **FastAPI integration for all major Iranian bank payment gateways** (درگاه‌های پرداخت بانکی ایران).

Drop 17 gateways into any FastAPI app in minutes — no database required, fully async, Pydantic v2.

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
- [GatewayManager Options](#gatewaymanager-options)
- [Error Handling](#error-handling)
- [Advanced Usage](#advanced-usage)
- [Writing a Custom Gateway](#writing-a-custom-gateway)
- [Testing & Sandbox](#testing--sandbox)
- [License](#license)

---

## Features

- **17 gateways** — all major Iranian bank PSPs and fintech aggregators
- **Unified interface** — one `GatewayManager` mounts all routes automatically
- **No database dependency** — you provide three async callbacks; the library handles the rest
- **Async-first** — built on `httpx` and FastAPI async routes throughout
- **SOAP gateways** supported via optional `zeep` dependency
- **Pydantic v2** models for type-safe configs and responses
- **Sandbox/test mode** — `sandbox=True` flag on every config
- **Duplicate payment detection** — `PaymentStatus.DUPLICATE` for idempotent retries
- **Auto-submit HTML forms** — Mellat, Saderat, Saman, Parsian handled transparently

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
# REST-only gateways (Zarinpal, IDPay, Zibal, Saderat, Pasargad, Saman, Melli, Irankish, Tejarat, Eghtesad Novin, NextPay, PayIr, PayPing, Vandar)
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
from fastapi import FastAPI
from fastapi_iranian_bank_gateways import GatewayManager, PaymentResult
from fastapi_iranian_bank_gateways.gateways import ZarinpalGateway, MellatGateway
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig
from fastapi_iranian_bank_gateways.gateways.tier1.mellat import MellatConfig

app = FastAPI()


# 1. Define your three async callbacks
async def get_order_info(order_id: str) -> dict:
    """Return the order amount and description from your database."""
    order = await db.orders.get(order_id)
    return {"amount": order.total_rials, "description": f"Order #{order_id}"}


async def on_success(result: PaymentResult) -> str:
    """Called after a successful bank verification. Return a redirect URL."""
    await db.orders.mark_paid(
        order_id=result.order_id,
        reference_id=result.reference_id,
        transaction_id=result.transaction_id,
    )
    return f"https://my-shop.com/orders/{result.order_id}/success"


async def on_failure(result: PaymentResult) -> str:
    """Called after a failed or cancelled payment. Return a redirect URL."""
    return f"https://my-shop.com/orders/{result.order_id}/failed?code={result.error_code}"


# 2. Configure your gateways
manager = GatewayManager(
    gateways=[
        ZarinpalGateway(ZarinpalConfig(
            merchant_id="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            sandbox=True,
        )),
        MellatGateway(MellatConfig(
            terminal_id=12345678,
            username="terminal_user",
            password="terminal_pass",
        )),
    ],
    get_order_info=get_order_info,
    on_success=on_success,
    on_failure=on_failure,
    prefix="/payments",
)

# 3. Mount the router — done!
app.include_router(manager.router)
```

This registers the following routes automatically:

```
POST /payments/zarinpal/pay        Initiate Zarinpal payment
GET  /payments/zarinpal/verify     Zarinpal bank callback (redirect)
POST /payments/mellat/pay          Initiate Mellat payment
POST /payments/mellat/verify       Mellat bank callback (form POST)
GET  /payments/{gateway}/verify    Generic GET callback (all gateways)
POST /payments/{gateway}/verify    Generic POST callback (all gateways)
```

---

## How It Works

### Payment Flow

```
Your frontend                  Your FastAPI app               Bank
     │                               │                          │
     │  POST /payments/zarinpal/pay  │                          │
     │ ──────────────────────────►  │                          │
     │                               │  POST to Zarinpal API   │
     │                               │ ──────────────────────► │
     │                               │  ◄── authority token ── │
     │  302 → bank payment page      │                          │
     │ ◄────────────────────────── │                          │
     │ ──────────────────────────────────────────────────────► │
     │                    (user fills card details)             │
     │                               │  GET /payments/zarinpal/verify?Authority=...&Status=OK
     │                               │ ◄──────────────────────────────────────────────────── │
     │                               │  POST verify to Zarinpal│
     │                               │ ──────────────────────► │
     │                               │  ◄── confirmed ──────── │
     │                               │  on_success() callback  │
     │  302 → your success page      │                          │
     │ ◄────────────────────────── │                          │
```

### Initiate a Payment

Send a `POST` request to `/{prefix}/{gateway}/pay`:

```bash
curl -X POST http://localhost:8000/payments/zarinpal/pay \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "ORDER-001",
    "amount": 100000,
    "callback_url": "https://my-shop.com/payments/zarinpal/verify",
    "mobile": "09123456789",
    "email": "user@example.com",
    "description": "Purchase order #001"
  }'
```

**Response:**
- **Redirect gateways** (Zarinpal, Pasargad, Sepah, IDPay, Zibal, NextPay, Pay.ir, PayPing, Vandar, Melli, Irankish, Tejarat, Eghtesad Novin): `302 Redirect` to the bank's payment page.
- **Form gateways** (Mellat, Saderat, Saman, Parsian): `200 HTML` page with a hidden auto-submit form that posts to the bank.

### Verify Callback

The bank redirects the user back to `/{prefix}/{gateway}/verify`. The library:
1. Parses the callback parameters
2. Calls `get_order_info(order_id)` to retrieve the expected amount
3. Calls `gateway.verify()` to confirm with the bank
4. Calls `on_success()` or `on_failure()` with a `PaymentResult`
5. Redirects the user to the URL returned by your callback

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
    sandbox=False,              # bool — use sandbox WSDL
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
from fastapi_iranian_bank_gateways.gateways.tier2.eghtesad_novin import EghtesadNovinConfig, EghtesadNovinGateway

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

Passed as the JSON body to `POST /{prefix}/{gateway}/pay`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `order_id` | `str` | Yes | Your unique order/invoice identifier |
| `amount` | `int` | Yes | Amount in **Rials (IRR)** — must be > 0 |
| `callback_url` | `str` | Yes | Full URL the bank will redirect back to |
| `currency` | `str` | No | `"IRR"` (default) or `"IRT"` |
| `mobile` | `str` | No | Payer mobile number (used for pre-filling) |
| `email` | `str` | No | Payer email address |
| `description` | `str` | No | Payment description shown on bank page |
| `metadata` | `dict` | No | Arbitrary extra data (passed through, not sent to bank) |

> All amounts are in **Rials (IRR)**. For example, 10,000 Tomans = 100,000 Rials.

---

## PaymentResult Fields

Returned to your `on_success` / `on_failure` callbacks.

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

## GatewayManager Options

```python
GatewayManager(
    gateways=[...],           # list[AbstractGateway] — at least one required
    get_order_info=...,       # async (order_id: str) -> dict
    on_success=...,           # async (result: PaymentResult) -> str (redirect URL)
    on_failure=...,           # async (result: PaymentResult) -> str (redirect URL)
    prefix="",                # str — URL prefix for all routes (default: no prefix)
    tags=["payments"],        # list[str] — OpenAPI tags
)
```

The `get_order_info` callback must return a dict with at least:
- `amount` — `int`, order amount in Rials (used by some gateways during verify)
- `description` — `str` (optional)

---

## Error Handling

All exceptions inherit from `GatewayError`.

```python
from fastapi_iranian_bank_gateways.exceptions import (
    GatewayError,             # base class
    GatewayConfigurationError,# bad or missing config
    GatewayConnectionError,   # network failure talking to bank
    GatewayAuthError,         # token/auth request failed
    GatewayPaymentError,      # bank rejected the payment
    MissingDependencyError,   # zeep not installed for a SOAP gateway
    DuplicatePaymentError,    # already verified (subclass of GatewayPaymentError)
)
```

Every exception exposes:
- `.gateway` — gateway slug where the error occurred
- `.code` — bank error code string (when available)
- `.raw` — raw bank response dict (on `GatewayPaymentError`)

### Catching errors in your callbacks

```python
from fastapi_iranian_bank_gateways.exceptions import GatewayConnectionError, GatewayPaymentError

async def on_failure(result: PaymentResult) -> str:
    # result.error_code contains the bank's error code
    # result.raw_response contains the full bank response
    await log_failed_payment(result.order_id, result.error_code, result.raw_response)
    return f"https://my-shop.com/failed?reason={result.error_code}"
```

### Handling SOAP missing dependency

```python
from fastapi_iranian_bank_gateways.exceptions import MissingDependencyError

try:
    await mellat_gateway.initiate(request)
except MissingDependencyError as e:
    # str(e) includes the install command
    print(e)
    # → zeep is required for SOAP-based gateways (Mellat, Sepah, Parsian).
    #   Install it with: pip install "fastapi-iranian-bank-gateways[soap]"
```

---

## Advanced Usage

### Multiple gateways, single manager

```python
from fastapi_iranian_bank_gateways.gateways import (
    ZarinpalGateway, IDPayGateway, MellatGateway,
    SaderatGateway, SamanGateway, ZibalGateway,
)

manager = GatewayManager(
    gateways=[
        ZarinpalGateway(ZarinpalConfig(merchant_id="...", sandbox=True)),
        IDPayGateway(IDPayConfig(api_key="...", sandbox=True)),
        MellatGateway(MellatConfig(terminal_id=123, username="u", password="p")),
        SaderatGateway(SaderatConfig(terminal_id="...")),
        SamanGateway(SamanConfig(terminal_id="...", password="...")),
        ZibalGateway(ZibalConfig(merchant="zibal")),
    ],
    get_order_info=get_order_info,
    on_success=on_success,
    on_failure=on_failure,
)
```

### Integrating with Dependency Injection

```python
from fastapi import FastAPI, Depends
from fastapi_iranian_bank_gateways import GatewayManager

app = FastAPI()

def get_manager() -> GatewayManager:
    # Could be cached, loaded from settings, etc.
    return GatewayManager(gateways=[...], ...)

app.include_router(get_manager().router, prefix="/pay")
```

### Using Pydantic Settings for config

```python
from pydantic_settings import BaseSettings
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig

class Settings(BaseSettings):
    zarinpal_merchant_id: str
    zarinpal_sandbox: bool = False

    model_config = {"env_file": ".env"}

settings = Settings()

zarinpal_config = ZarinpalConfig(
    merchant_id=settings.zarinpal_merchant_id,
    sandbox=settings.zarinpal_sandbox,
)
```

`.env` file:
```
ZARINPAL_MERCHANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ZARINPAL_SANDBOX=true
```

### Accessing the gateway registry

```python
manager = GatewayManager(gateways=[zarinpal, mellat], ...)

# Direct gateway access (e.g. for custom verification logic)
zarinpal = manager._registry["zarinpal"]
```

### Custom callback URL per request

The `callback_url` in `PaymentRequest` is per-request, so you can construct it dynamically:

```python
import httpx

async with httpx.AsyncClient() as client:
    await client.post("http://localhost:8000/payments/zarinpal/pay", json={
        "order_id": "ORDER-42",
        "amount": 500000,
        "callback_url": f"https://my-shop.com/payments/zarinpal/verify?order={order_id}",
    })
```

---

## Writing a Custom Gateway

Subclass `AbstractGateway` to add a gateway not included in this package:

```python
from typing import ClassVar
from fastapi_iranian_bank_gateways.base.gateway import AbstractGateway
from fastapi_iranian_bank_gateways.base.config import BaseGatewayConfig
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest, InitiateResponse, RedirectInitiateResponse
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
            })
        data = resp.json()
        return PaymentResult(
            status=PaymentStatus.SUCCESS if data["ok"] else PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=str(raw.get("ref", "")),
            reference_id=data.get("rrn"),
            raw_response=data,
        )


# Use it like any built-in gateway
manager = GatewayManager(
    gateways=[MyBankGateway(MyBankConfig(api_key="...", sandbox=False))],
    get_order_info=get_order_info,
    on_success=on_success,
    on_failure=on_failure,
)
```

---

## Testing & Sandbox

### Sandbox mode

Every gateway config accepts `sandbox=True` to point to test/sandbox endpoints:

```python
ZarinpalConfig(merchant_id="...", sandbox=True)   # → sandbox.zarinpal.com
IDPayConfig(api_key="...", sandbox=True)           # → adds X-SANDBOX: 1 header
MellatConfig(..., sandbox=True)                    # → bpms.bpi.ir WSDL
ZibalConfig(merchant="zibal")                      # use literal "zibal" for sandbox
PayIrConfig(api="test")                            # use literal "test" as api key
```

### Testing your FastAPI app

```python
import pytest
from fastapi.testclient import TestClient
from fastapi_iranian_bank_gateways import GatewayManager, PaymentResult
from fastapi_iranian_bank_gateways.gateways import ZarinpalGateway
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig

@pytest.fixture
def client():
    app = FastAPI()

    async def get_order_info(order_id): return {"amount": 100000}
    async def on_success(r): return f"https://shop.com/ok/{r.order_id}"
    async def on_failure(r): return f"https://shop.com/fail/{r.order_id}"

    manager = GatewayManager(
        gateways=[ZarinpalGateway(ZarinpalConfig(merchant_id="test-id", sandbox=True))],
        get_order_info=get_order_info,
        on_success=on_success,
        on_failure=on_failure,
        prefix="/payments",
    )
    app.include_router(manager.router)
    return TestClient(app, follow_redirects=False)
```

### Mocking HTTP calls in unit tests

Use [respx](https://lundberg.github.io/respx/) to mock httpx:

```python
import httpx
import respx
from fastapi_iranian_bank_gateways.gateways import ZarinpalGateway
from fastapi_iranian_bank_gateways.gateways.tier3.zarinpal import ZarinpalConfig
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

@respx.mock
@pytest.mark.asyncio
async def test_zarinpal_initiate():
    respx.post("https://sandbox.zarinpal.com/pg/v4/payment/request.json").mock(
        return_value=httpx.Response(200, json={
            "data": {"code": 100, "authority": "A000000000000000000000001234567890"},
            "errors": [],
        })
    )
    gateway = ZarinpalGateway(ZarinpalConfig(merchant_id="test-id", sandbox=True))
    result = await gateway.initiate(PaymentRequest(
        order_id="TEST-001",
        amount=100000,
        callback_url="https://shop.com/verify",
    ))
    assert result.type == "redirect"
    assert "A000000000000000000000001234567890" in result.url
```

---

## Project Structure

```
src/fastapi_iranian_bank_gateways/
├── __init__.py           GatewayManager, models, exceptions (public API)
├── manager.py            GatewayManager + FastAPI router factory
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
5. Document the config fields in this README and in `memory/gateway_reference.md`
