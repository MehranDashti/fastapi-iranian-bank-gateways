from typing import ClassVar

import httpx

from ....base.gateway import AbstractGateway
from ....exceptions.errors import GatewayAuthError, GatewayConnectionError, GatewayPaymentError
from ....models.callback import BankCallbackData, PaymentResult
from ....models.enums import PaymentStatus
from ....models.payment import InitiateResponse, PaymentRequest, RedirectInitiateResponse
from .config import PasargadConfig


class PasargadGateway(AbstractGateway):
    """
    Pasargad Bank — REST with Bearer token, server-side redirect, GET callback.
    Verify is two-step: check_verify then verify.
    """

    gateway_slug: ClassVar[str] = "pasargad"
    config_class: ClassVar[type] = PasargadConfig
    callback_method: ClassVar[str] = "GET"

    def __init__(self, config: PasargadConfig) -> None:
        super().__init__(config)
        self.config: PasargadConfig = config

    async def _get_bearer_token(self) -> str:
        payload = {"username": self.config.username, "password": self.config.password}
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(
                    self.config.token_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        token = data.get("token")
        if token:
            return str(token)
        raise GatewayAuthError(
            f"Pasargad token request failed: {data}",
            gateway=self.gateway_slug,
        )

    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        token = await self._get_bearer_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        payload = {
            "amount": request.amount,
            "callbackApi": request.callback_url,
            "invoice": request.order_id,
            "invoiceDate": "",
            "mobileNumber": request.mobile or "",
            "payerName": "",
            "serviceCode": 8,
            "serviceType": "PURCHASE",
            "terminalNumber": self.config.terminal_number,
            "nationalCode": None,
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(
                    self.config.purchase_url, json=payload, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        if data.get("resultCode") == 0:
            return RedirectInitiateResponse(url=data["data"]["url"])
        raise GatewayPaymentError(
            f"Pasargad payment initiation failed: {data}",
            gateway=self.gateway_slug,
            code=str(data.get("resultCode", "")),
            raw=data,
        )

    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        """Two-step verify: check_verify then verify."""
        raw = callback_data.raw
        order_id = str(raw.get("iN", raw.get("_order_id", "")))
        tref = str(raw.get("tref", ""))
        url_id = str(raw.get("iD", ""))

        token = await self._get_bearer_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        # Step 1: check_verify
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                check_resp = await client.post(
                    self.config.check_verify_url,
                    json={"invoiceId": order_id},
                    headers=headers,
                )
                check_resp.raise_for_status()
                check_data = check_resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        if check_data.get("resultCode") != 0:
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                error_code=str(check_data.get("resultCode", "")),
                raw_response=check_data,
            )

        # Step 2: verify/capture
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                verify_resp = await client.post(
                    self.config.verify_url,
                    json={"invoice": order_id, "urlId": url_id},
                    headers=headers,
                )
                verify_resp.raise_for_status()
                verify_data = verify_resp.json()
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(str(exc), gateway=self.gateway_slug) from exc

        if verify_data.get("resultCode") == 0:
            return PaymentResult(
                status=PaymentStatus.SUCCESS,
                gateway_slug=self.gateway_slug,
                order_id=order_id,
                reference_id=tref,
                raw_response=verify_data,
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.gateway_slug,
            order_id=order_id,
            error_code=str(verify_data.get("resultCode", "")),
            raw_response=verify_data,
        )
