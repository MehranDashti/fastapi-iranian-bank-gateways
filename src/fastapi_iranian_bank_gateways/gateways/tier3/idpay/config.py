from ....base.config import BaseGatewayConfig


class IDPayConfig(BaseGatewayConfig):
    api_key: str

    @property
    def payment_url(self) -> str:
        return "https://api.idpay.ir/v1.1/payment"

    @property
    def verify_url(self) -> str:
        return "https://api.idpay.ir/v1.1/payment/verify"

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json", "X-API-KEY": self.api_key}
        if self.sandbox:
            h["X-SANDBOX"] = "1"
        return h
