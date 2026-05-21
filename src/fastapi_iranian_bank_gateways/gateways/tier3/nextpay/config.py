from ....base.config import BaseGatewayConfig


class NextPayConfig(BaseGatewayConfig):
    api_key: str

    @property
    def token_url(self) -> str:
        return "https://nextpay.org/nx/gateway/token"

    @property
    def gateway_url(self) -> str:
        return "https://nextpay.org/nx/gateway/payment/"

    @property
    def verify_url(self) -> str:
        return "https://nextpay.org/nx/gateway/verify"
