---
name: implementation-notes
description: Edge cases, quirks, and implementation decisions made during development
metadata:
  type: project
---

# Implementation Notes

## Pasargad Two-Step Verify
Pasargad requires two sequential REST calls on the callback:
1. `check_verify` (CheckTransactionResult) — checks if payment succeeded
2. `verify` (VerifyPayment) — confirms/captures the payment

Both happen inside `PasargadGateway.verify()` so the `GatewayManager` interface stays uniform.

## SOAP Optional Dependency
- Mellat, Sepah, Parsian require zeep
- `utils/soap.py:get_soap_client()` does `try: import zeep` at call time
- Raises `MissingDependencyError` with: `pip install "fastapi-iranian-bank-gateways[soap]"`
- Import of the gateway class itself is always fine; error only on first actual call

## Amount Handling for Zarinpal Verify
Zarinpal's verify endpoint requires the expected amount (to detect tampered amounts).
The `GatewayManager._handle_verify()` calls `get_order_info(order_id)` to retrieve amount,
then passes it via `callback_data.raw["_amount"]` (internal key, prefixed with `_` to avoid collision).
The order_id is extracted from Zarinpal's callback via a convention (stored in metadata or state).

## Currency
- All amounts are in **Rials (IRR)** internally — the smallest unit
- Zarinpal historically used Tomans; v4 API uses Rials — no conversion needed for v4
- IDPay uses Rials
- Users should pass amounts in Rials

## Form vs Redirect
- `FormInitiateResponse` → `HTMLResponse` with auto-submit form
- `RedirectInitiateResponse` → `RedirectResponse(302)`
- `GatewayManager._build_router()` switches on isinstance

## Duplicate Payment (Idempotency)
- Mellat ResCode `43` → `PaymentStatus.DUPLICATE`
- Zarinpal code `101` → `PaymentStatus.DUPLICATE`
- IDPay status `200` → `PaymentStatus.DUPLICATE`
- Zibal result `201` → `PaymentStatus.DUPLICATE`
- `GatewayManager._handle_verify()` treats DUPLICATE same as SUCCESS (calls `on_success`)

## Sandbox Flags
- Each config has `sandbox: bool = False`
- Zarinpal sandbox: different subdomain (`sandbox.zarinpal.com`)
- IDPay sandbox: same URL, `X-SANDBOX: 1` header
- Mellat sandbox: different WSDL host
- Sepah sandbox: same WSDL
- Others: determined by gateway docs

## httpx vs requests
Reference app uses blocking `requests`. This package uses `httpx.AsyncClient` as async context manager per call. No connection pooling at package level (user's app manages its own lifecycle).

## Thread Safety
`GatewayManager._registry` is read-only after construction. All gateway methods use `httpx.AsyncClient` as context managers (no shared mutable state). Safe for concurrent async requests.
