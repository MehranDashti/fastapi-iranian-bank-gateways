from ....base.config import BaseGatewayConfig


class EghtesadNovinConfig(BaseGatewayConfig):
    username: str
    password: str
    merchant_id: str

    @property
    def token_url(self) -> str:
        return "https://ipg.en-bank.ir/igprest/api/v1/merchants/token"

    @property
    def gateway_url(self) -> str:
        return "https://ipg.en-bank.ir"

    @property
    def verify_url(self) -> str:
        return "https://ipg.en-bank.ir/igprest/api/v1/merchants/verify"
