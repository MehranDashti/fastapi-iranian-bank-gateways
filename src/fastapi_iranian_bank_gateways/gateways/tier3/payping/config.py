from ....base.config import BaseGatewayConfig


class PayPingConfig(BaseGatewayConfig):
    access_token: str

    @property
    def request_url(self) -> str:
        return "https://api.payping.ir/v2/pay"

    @property
    def gateway_url(self) -> str:
        return "https://api.payping.ir/v2/pay/gotoipg/"

    @property
    def verify_url(self) -> str:
        return "https://api.payping.ir/v2/pay/verify"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
