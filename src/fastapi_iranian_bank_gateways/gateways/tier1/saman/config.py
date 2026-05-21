from ....base.config import BaseGatewayConfig


class SamanConfig(BaseGatewayConfig):
    terminal_id: str
    password: str

    @property
    def token_url(self) -> str:
        return "https://sep.shaparak.ir/onlinepg/onlinepg"

    @property
    def gateway_url(self) -> str:
        return "https://sep.shaparak.ir/OnlinePG/OnlinePG"

    @property
    def verify_url(self) -> str:
        return "https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction"
