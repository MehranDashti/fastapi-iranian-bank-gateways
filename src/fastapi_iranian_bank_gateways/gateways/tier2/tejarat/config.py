from ....base.config import BaseGatewayConfig


class TejaratConfig(BaseGatewayConfig):
    terminal_id: str

    @property
    def token_url(self) -> str:
        return "https://agt.tejaratpay.com/ipg/api/v1/token"

    @property
    def gateway_url(self) -> str:
        return "https://agt.tejaratpay.com/ipg/index"

    @property
    def verify_url(self) -> str:
        return "https://agt.tejaratpay.com/ipg/api/v1/payment"
