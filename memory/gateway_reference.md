---
name: gateway-reference
description: Per-gateway API endpoints, credential fields, and callback parameters
metadata:
  type: reference
---

# Gateway API Reference

## Mellat (به‌پرداخت ملت)
- **Protocol:** SOAP via zeep
- **Credentials:** `terminal_id` (int), `username` (str), `password` (str)
- **Token WSDL:** `https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl`
- **Sandbox WSDL:** `https://bpms.bpi.ir/pgwchannel/services/pgw?wsdl`
- **Gateway URL:** `https://bpm.shaparak.ir/pgwchannel/startpay.mellat`
- **Flow:** SOAP `bpPayRequest` → RefId → HTML form → bank → POST callback with `ResCode`, `SaleOrderId`, `SaleReferenceId`
- **Verify:** SOAP `bpVerifyRequest`; ResCode `0`=success, `43`=duplicate

## Saderat (پرداخت الکترونیک صادرات ایران)
- **Protocol:** REST
- **Credentials:** `terminal_id` (str)
- **Token URL:** `https://mabna.shaparak.ir:8080/V1/PeymentApi/GetToken`
- **Gateway URL:** `https://mabna.shaparak.ir:8080/V1/PeymentApi/PaymentRequest`
- **Verify URL:** `https://mabna.shaparak.ir:8080/V1/PeymentApi/Advice`
- **Flow:** REST token → HTML form → bank → GET callback with `digitalreceipt`, `respcode`
- **Verify:** POST with `digitalreceipt`, `terminalid`; respcode `0`=success

## Pasargad (پاسارگاد)
- **Protocol:** REST with Bearer token
- **Credentials:** `username` (str), `password` (str), `terminal_number` (str), `merchant_code` (str)
- **Token URL:** `https://pep.shaparak.ir/Api/v1/Payment/GetToken`
- **Purchase URL:** `https://pep.shaparak.ir/Api/v1/Payment/GetUrlAndToken`
- **Check Verify URL:** `https://pep.shaparak.ir/Api/v1/Payment/CheckTransactionResult`
- **Verify URL:** `https://pep.shaparak.ir/Api/v1/Payment/VerifyPayment`
- **Flow:** REST Bearer token → redirect → GET callback with `iN`, `iD`, `tref`
- **Verify (2-step):** `check_verify` (CheckTransactionResult) then `verify` (VerifyPayment)

## Saman (سامان)
- **Protocol:** REST
- **Credentials:** `terminal_id` (str), `password` (str)
- **Token URL:** `https://sep.shaparak.ir/onlinepg/onlinepg`
- **Gateway URL:** `https://sep.shaparak.ir/OnlinePG/OnlinePG`
- **Verify URL:** `https://verify.sep.ir/Payments/ReferencePayment.asmx`
- **Flow:** REST token → HTML form → bank → GET callback with `RefNum`, `State`, `MID`, `TerminalId`
- **Verify:** SOAP or REST; State `OK`=success

## Sepah (سپه)
- **Protocol:** SOAP via zeep
- **Credentials:** `login_account` (str)
- **WSDL:** `https://sepehr.shaparak.ir:8081/ws/MerchantService?wsdl`
- **Gateway URL:** `https://sepehr.shaparak.ir:8080/Pay`
- **Flow:** SOAP `SalePaymentRequest` → Token → redirect → POST callback with `Token`, `status`, `OrderId`
- **Verify:** SOAP `ConfirmPayment`; status `1`=success

## Parsian (پارسیان)
- **Protocol:** SOAP via zeep
- **Credentials:** `login_account` (str)
- **Token WSDL:** `https://pec.shaparak.ir/NewIPGServices/Sale/SaleService.asmx?wsdl`
- **Confirm WSDL:** `https://pec.shaparak.ir/NewIPGServices/Confirm/ConfirmService.asmx?wsdl`
- **Gateway URL:** `https://pec.shaparak.ir/NewIPG/?Token=`
- **Flow:** SOAP `SalePaymentRequest` → Token → HTML form / redirect → POST callback with `Token`, `status`, `RRN`
- **Verify:** SOAP `ConfirmPayment`

## Melli / Behpardakht (به‌پرداخت ملی)
- **Protocol:** REST
- **Credentials:** `terminal_id` (str), `merchant_id` (str)
- **Token URL:** `https://bpm.shaparak.ir/pgwchannel/services/rest/PaymentTokenRequest`
- **Gateway URL:** `https://bpm.shaparak.ir/pgwchannel/startpay.mellat`
- **Verify URL:** `https://bpm.shaparak.ir/pgwchannel/services/rest/VerifyPayment`

## Irankish (ایران کیش)
- **Protocol:** REST
- **Credentials:** `terminal_id` (str), `acceptor_id` (str), `pass_phrase` (str)
- **Token URL:** `https://ikc.shaparak.ir/TToken/Tokens.ngx`
- **Gateway URL:** `https://ikc.shaparak.ir/TPayment/Payment.ngx`
- **Verify URL:** `https://ikc.shaparak.ir/TVerify/Verify.ngx`

## Tejarat (تجارت)
- **Protocol:** REST
- **Credentials:** `terminal_id` (str)
- **Token URL:** `https://agt.tejaratpay.com/ipg/api/v1/token`
- **Gateway URL:** `https://agt.tejaratpay.com/ipg/index`
- **Verify URL:** `https://agt.tejaratpay.com/ipg/api/v1/payment`

## Eghtesad Novin (اقتصاد نوین)
- **Protocol:** REST
- **Credentials:** `username` (str), `password` (str), `merchant_id` (str)
- **Token URL:** `https://ipg.en-bank.ir/igprest/api/v1/merchants/token`
- **Gateway URL:** `https://ipg.en-bank.ir`
- **Verify URL:** `https://ipg.en-bank.ir/igprest/api/v1/merchants/verify`

## Zarinpal (زرین‌پال)
- **Protocol:** REST/JSON
- **Credentials:** `merchant_id` (36-char UUID str)
- **Payment URL:** `https://www.zarinpal.com/pg/v4/payment/request.json`
- **Sandbox Payment URL:** `https://sandbox.zarinpal.com/pg/v4/payment/request.json`
- **Verify URL:** `https://www.zarinpal.com/pg/v4/payment/verify.json`
- **Start Pay URL:** `https://www.zarinpal.com/pg/StartPay/`
- **Flow:** POST → authority → redirect → GET callback with `Authority`, `Status`
- **Verify:** POST with merchant_id, authority, amount; code `100`=success, `101`=duplicate

## IDPay (آیدی پی)
- **Protocol:** REST/JSON
- **Credentials:** `api_key` (str)
- **Payment URL:** `https://api.idpay.ir/v1.1/payment`
- **Sandbox Payment URL:** `https://api.idpay.ir/v1.1/payment` (with `X-SANDBOX: 1` header)
- **Verify URL:** `https://api.idpay.ir/v1.1/payment/verify`
- **Flow:** POST → link → redirect → POST callback with `id`, `order_id`, `status`
- **Verify:** status `100`=success, `101`=not paid, `200`=already verified

## Zibal (زیبال)
- **Protocol:** REST/JSON
- **Credentials:** `merchant` (str)
- **Request URL:** `https://gateway.zibal.ir/v1/request`
- **Start URL:** `https://gateway.zibal.ir/start/{track_id}`
- **Verify URL:** `https://gateway.zibal.ir/v1/verify`
- **Flow:** POST → trackId → redirect → GET callback with `trackId`, `success`, `orderId`
- **Verify:** result `100`=success, `201`=already verified

## NextPay (نکست پی)
- **Protocol:** REST/JSON
- **Credentials:** `api_key` (str)
- **Request URL:** `https://nextpay.org/nx/gateway/token`
- **Gateway URL:** `https://nextpay.org/nx/gateway/payment/`
- **Verify URL:** `https://nextpay.org/nx/gateway/verify`
- **Flow:** POST → trans_id → redirect → GET callback with `trans_id`, `order_id`, `amount`
- **Verify:** code `-90`=success, `0`=already verified

## Pay.ir
- **Protocol:** REST/JSON
- **Credentials:** `api` (str)
- **Send URL:** `https://pay.ir/pg/send`
- **Gateway URL:** `https://pay.ir/pg/`
- **Verify URL:** `https://pay.ir/pg/verify`
- **Flow:** POST → token → redirect → GET callback with `token`, `status`
- **Verify:** status `1`=success

## PayPing
- **Protocol:** REST/JSON
- **Credentials:** `access_token` (str)
- **Request URL:** `https://api.payping.ir/v2/pay`
- **Gateway URL:** `https://api.payping.ir/v2/pay/gotoipg/`
- **Verify URL:** `https://api.payping.ir/v2/pay/verify`
- **Flow:** POST → code → redirect → GET callback with `code`, `refid`
- **Verify:** POST with amount, refId

## Vandar
- **Protocol:** REST/JSON
- **Credentials:** `api_key` (str)
- **Send URL:** `https://ipg.vandar.io/api/v3/send`
- **Gateway URL:** `https://ipg.vandar.io/v3/`
- **Verify URL:** `https://ipg.vandar.io/api/v3/verify`
- **Flow:** POST → token → redirect → POST callback with `token`, `payment_status`
- **Verify:** payment_status `DONE`=success
