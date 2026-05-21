from ....base.config import BaseGatewayConfig


class PayIrConfig(BaseGatewayConfig):
    api: str

    @property
    def send_url(self) -> str:
        return "https://pay.ir/pg/send"

    @property
    def gateway_url(self) -> str:
        return "https://pay.ir/pg/"

    @property
    def verify_url(self) -> str:
        return "https://pay.ir/pg/verify"
