from ....base.config import BaseGatewayConfig


class ZibalConfig(BaseGatewayConfig):
    merchant: str  # use "zibal" for sandbox testing

    @property
    def request_url(self) -> str:
        return "https://gateway.zibal.ir/v1/request"

    @property
    def verify_url(self) -> str:
        return "https://gateway.zibal.ir/v1/verify"

    @property
    def start_url(self) -> str:
        return "https://gateway.zibal.ir/start/"
