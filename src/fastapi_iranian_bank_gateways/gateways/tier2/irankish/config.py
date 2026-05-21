from ....base.config import BaseGatewayConfig


class IrankishConfig(BaseGatewayConfig):
    terminal_id: str
    acceptor_id: str
    pass_phrase: str

    @property
    def token_url(self) -> str:
        return "https://ikc.shaparak.ir/TToken/Tokens.ngx"

    @property
    def gateway_url(self) -> str:
        return "https://ikc.shaparak.ir/TPayment/Payment.ngx"

    @property
    def verify_url(self) -> str:
        return "https://ikc.shaparak.ir/TVerify/Verify.ngx"
