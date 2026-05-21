from ....base.config import BaseGatewayConfig


class VandarConfig(BaseGatewayConfig):
    api_key: str

    @property
    def send_url(self) -> str:
        return "https://ipg.vandar.io/api/v3/send"

    @property
    def gateway_url(self) -> str:
        return "https://ipg.vandar.io/v3/"

    @property
    def verify_url(self) -> str:
        return "https://ipg.vandar.io/api/v3/verify"
