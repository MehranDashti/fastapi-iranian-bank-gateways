# CLAUDE.md — fastapi-iranian-bank-gateways

This file is the persistent memory and orientation guide for Claude Code working in this repository. Update it whenever architecture decisions, conventions, or project state change.

---

## Project Identity

**Package name:** `fastapi-iranian-bank-gateways`  
**Import name:** `fastapi_iranian_bank_gateways`  
**Purpose:** Pip-installable FastAPI integration for all major Iranian bank payment gateways  
**Version:** 0.1.0  
**Python:** ≥ 3.10  
**Install:** `pip install fastapi-iranian-bank-gateways` (REST) / `pip install "fastapi-iranian-bank-gateways[soap]"` (+ SOAP)

---

## Repository Layout

```
fastapi-iranian-bank-gateways/
├── CLAUDE.md                    ← you are here
├── README.md
├── LICENSE
├── pyproject.toml               ← hatchling build, deps, extras
├── memory/                      ← extended project memory (not gitignored)
│   ├── MEMORY.md                ← index
│   ├── project_overview.md      ← goals, status, architecture
│   ├── gateway_reference.md     ← per-gateway endpoints & credential fields
│   └── implementation_notes.md  ← edge cases, quirks, decisions
├── src/
│   └── fastapi_iranian_bank_gateways/
│       ├── __init__.py          ← public API surface
│       ├── py.typed             ← PEP 561 marker
│       ├── manager.py           ← GatewayManager + FastAPI router factory
│       ├── base/
│       │   ├── gateway.py       ← AbstractGateway ABC
│       │   └── config.py        ← BaseGatewayConfig (Pydantic v2, frozen=True)
│       ├── models/
│       │   ├── payment.py       ← PaymentRequest, FormInitiateResponse, RedirectInitiateResponse
│       │   ├── callback.py      ← BankCallbackData, PaymentResult
│       │   └── enums.py         ← PaymentStatus, Currency, GatewayType
│       ├── exceptions/
│       │   └── errors.py        ← GatewayError hierarchy
│       ├── utils/
│       │   ├── http.py          ← post_json / get_json (httpx)
│       │   ├── soap.py          ← lazy zeep import with MissingDependencyError
│       │   └── form.py          ← render_auto_submit_form (Jinja2)
│       ├── templates/
│       │   └── generic_form.html ← RTL auto-submit form template
│       └── gateways/
│           ├── __init__.py      ← re-exports all 17 gateway classes
│           ├── tier1/           ← Mellat, Saderat, Pasargad, Saman, Sepah
│           ├── tier2/           ← Parsian, Melli, Irankish, Tejarat, EghtesadNovin
│           └── tier3/           ← Zarinpal, IDPay, Zibal, NextPay, PayIr, PayPing, Vandar
└── tests/
    ├── conftest.py
    ├── unit/                    ← 21 test files, one per gateway + shared
    └── integration/
        └── test_full_flow.py    ← TestClient full initiate→verify→redirect cycle
```

Each gateway subdirectory (`gateways/tier{N}/{name}/`) always contains:
- `gateway.py` — `{Name}Gateway(AbstractGateway)` class
- `config.py` — `{Name}Config(BaseGatewayConfig)` class
- `__init__.py` — re-exports both

---

## Architecture

### Core Pattern

```
User's FastAPI app
    └── GatewayManager(gateways=[...], get_order_info, on_success, on_failure)
            └── APIRouter
                    ├── POST /{gateway}/pay    → gateway.initiate() → HTMLResponse | RedirectResponse
                    ├── GET  /{gateway}/verify → gateway.verify()   → RedirectResponse
                    └── POST /{gateway}/verify → gateway.verify()   → RedirectResponse
```

### AbstractGateway Interface

Every gateway implements exactly two async methods:

```python
async def initiate(self, request: PaymentRequest) -> InitiateResponse
async def verify(self, callback_data: BankCallbackData) -> PaymentResult
```

And declares three class variables:
```python
gateway_slug: ClassVar[str]          # "mellat", "zarinpal", etc.
config_class: ClassVar[type]         # The Pydantic config class
callback_method: ClassVar[str]       # "GET" or "POST"
```

### Response Types

- `FormInitiateResponse(html=...)` → `HTMLResponse` (Mellat, Saderat, Saman, Parsian)
- `RedirectInitiateResponse(url=...)` → `RedirectResponse(302)` (all others)

### GatewayManager Callbacks

Users provide three async callables — no database dependency in the library:

```python
get_order_info(order_id: str) -> dict   # must return {"amount": int, ...}
on_success(result: PaymentResult) -> str  # returns redirect URL
on_failure(result: PaymentResult) -> str  # returns redirect URL
```

### SOAP Gateways

Mellat, Sepah, Parsian use SOAP via `zeep`. The import is **lazy** — `utils/soap.py:get_soap_client()` raises `MissingDependencyError` at call time if zeep is absent, with a clear install hint. Importing the gateway class itself never fails.

### Pasargad Two-Step Verify

Pasargad requires `check_verify` then `verify` sequentially. Both are handled inside `PasargadGateway.verify()` — the external interface is identical to all other gateways.

---

## Implemented Gateways (17 total)

| Slug | Class | Tier | Protocol | Callback |
|------|-------|------|----------|----------|
| `mellat` | `MellatGateway` | 1 | SOAP | POST |
| `saderat` | `SaderatGateway` | 1 | REST | GET |
| `pasargad` | `PasargadGateway` | 1 | REST | GET |
| `saman` | `SamanGateway` | 1 | REST | GET |
| `sepah` | `SepahGateway` | 1 | SOAP | POST |
| `parsian` | `ParsianGateway` | 2 | SOAP | POST |
| `melli` | `MelliGateway` | 2 | REST | POST |
| `irankish` | `IrankishGateway` | 2 | REST | POST |
| `tejarat` | `TejaratGateway` | 2 | REST | POST |
| `eghtesad_novin` | `EghtesadNovinGateway` | 2 | REST | POST |
| `zarinpal` | `ZarinpalGateway` | 3 | REST/JSON | GET |
| `idpay` | `IDPayGateway` | 3 | REST/JSON | POST |
| `zibal` | `ZibalGateway` | 3 | REST/JSON | GET |
| `nextpay` | `NextPayGateway` | 3 | REST/JSON | GET |
| `pay_ir` | `PayIrGateway` | 3 | REST/JSON | GET |
| `payping` | `PayPingGateway` | 3 | REST/JSON | GET |
| `vandar` | `VandarGateway` | 3 | REST/JSON | POST |

---

## Key Conventions

### Adding a New Gateway

1. Create `src/fastapi_iranian_bank_gateways/gateways/tier{N}/{slug}/`
2. Write `config.py` — extend `BaseGatewayConfig`, add `@property` for URLs
3. Write `gateway.py` — extend `AbstractGateway`, implement `initiate()` and `verify()`
4. Write `__init__.py` — re-export both classes
5. Add to parent `tier{N}/__init__.py` and `gateways/__init__.py`
6. Add to `src/fastapi_iranian_bank_gateways/__init__.py` if it should be in the public API
7. Write tests in `tests/unit/test_{slug}.py`
8. Add gateway reference info to `memory/gateway_reference.md`
9. Update the gateway table in `CLAUDE.md` and `README.md`

### Amounts

All amounts are in **Rials (IRR)**. Exception: PayPing uses Tomans internally — the gateway divides by 10 before sending to the API. Do not add currency conversion elsewhere.

### HTTP Calls

Use `httpx.AsyncClient` as an async context manager per call in individual gateways. `utils/http.py:post_json()` / `get_json()` support optional `client` injection, `max_retries`, and `retry_backoff` — only `TimeoutException` and `NetworkError` are retried (never 4xx/5xx). For connection pooling at app level, use `GatewayManager` as an async context manager in FastAPI lifespan (opens a shared `httpx.AsyncClient` with limits).

### Config Objects

All configs are Pydantic v2 models with `model_config = {"frozen": True}`. URLs are computed as `@property` (not stored fields) so `sandbox=True` automatically switches them. Never store mutable state on configs.

### Error Codes

Map all bank-specific error codes to `PaymentStatus` in `verify()`:
- `DUPLICATE` for "already verified" codes (Mellat `43`, Zarinpal `101`, IDPay `200`, Zibal `201`)
- `CANCELLED` when the user explicitly aborted (Zarinpal `Status != OK`, Pay.ir `status != 1`)
- `FAILED` for all other non-success codes

---

## Dependencies

| Package | Purpose | Optional |
|---------|---------|----------|
| `fastapi>=0.100.0` | Router, responses | No |
| `pydantic>=2.0.0` | Models and validation | No |
| `httpx>=0.24.0` | Async HTTP for REST gateways | No |
| `jinja2>=3.1.0` | Auto-submit HTML form templates | No |
| `zeep>=4.1.0` | SOAP for Mellat, Sepah, Parsian | Yes — `[soap]` |
| `lxml>=4.9.0` | XML parser required by zeep | Yes — `[soap]` |

Dev deps: `pytest`, `pytest-asyncio`, `respx` (httpx mocker), `pytest-cov`, `ruff`, `mypy`, `pre-commit`

---

## Running Tests

```bash
# Install with dev + SOAP dependencies
pip install -e ".[dev,soap]"
# or
make install

# Run all tests with coverage
make test            # pytest tests/ -v (includes --cov)
make coverage        # same + HTML report in htmlcov/

# Run a specific file
python3 -m pytest tests/unit/test_zarinpal.py -v
```

Tests use `respx` to mock all httpx calls. SOAP gateways use `unittest.mock.MagicMock` to patch `get_soap_client` at the gateway module's import path (not at `utils.soap`).

Current status: **113 tests, 113 passing, ~90% coverage.**

---

## CI/CD

```bash
make lint         # ruff check src/ tests/
make type-check   # mypy src/
make format       # ruff format + ruff check --fix
make build        # python -m build → dist/
make pre-commit   # install hooks + run all
```

**GitHub Actions** (`.github/workflows/`):
- `test.yml` — runs on push/PR: lint → type-check → pytest (matrix: Python 3.10, 3.11, 3.12)
- `publish.yml` — triggers on `v*.*.*` tags: builds wheel + sdist, publishes via OIDC Trusted Publisher, creates GitHub Release

**PyPI setup:** Configure a Trusted Publisher in your PyPI project settings (no `PYPI_API_TOKEN` secret needed). Set the environment name to `pypi` in the repo settings.

**Dependabot** (`.github/dependabot.yml`): weekly pip + GitHub Actions updates.

---

## Memory Files

Extended memory lives in `memory/` — read these for deeper context:

- `memory/project_overview.md` — goals, architecture decisions, implementation status
- `memory/gateway_reference.md` — per-gateway API endpoints, credential fields, response codes
- `memory/implementation_notes.md` — edge cases, quirks, and non-obvious implementation decisions

**Always update memory files when:**
- A new gateway is added or modified
- A bug is discovered and fixed in a gateway's verify/initiate logic
- A bank changes its API (URL, field names, response format)
- A new architectural decision is made

---

## Reference Implementation

The original app at `/test/agamemnon` contains 5 gateways as procedural adapters (not a package). It was used as the source of truth for Tier 1 gateway API details. If a Tier 1 gateway's behavior seems wrong, cross-reference with:

- `/test/agamemnon/app/adapters/{name}_adapter.py`
- `/test/agamemnon/app/strategies/payment_sterategy.py`
- `/test/agamemnon/resources/*.html` (form templates)
