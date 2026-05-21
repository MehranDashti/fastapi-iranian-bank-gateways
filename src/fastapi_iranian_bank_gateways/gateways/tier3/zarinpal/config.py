from ....base.config import BaseGatewayConfig


class ZarinpalConfig(BaseGatewayConfig):
    merchant_id: str  # 36-character UUID

    @property
    def _base(self) -> str:
        return "sandbox.zarinpal.com" if self.sandbox else "www.zarinpal.com"

    @property
    def payment_url(self) -> str:
        return f"https://{self._base}/pg/v4/payment/request.json"

    @property
    def verify_url(self) -> str:
        return f"https://{self._base}/pg/v4/payment/verify.json"

    @property
    def start_pay_url(self) -> str:
        return f"https://{self._base}/pg/StartPay/"
