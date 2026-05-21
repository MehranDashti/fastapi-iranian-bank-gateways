from ....base.config import BaseGatewayConfig


class SaderatConfig(BaseGatewayConfig):
    terminal_id: str

    @property
    def token_url(self) -> str:
        return "https://mabna.shaparak.ir:8080/V1/PeymentApi/GetToken"

    @property
    def gateway_url(self) -> str:
        return "https://mabna.shaparak.ir:8080/V1/PeymentApi/PaymentRequest"

    @property
    def verify_url(self) -> str:
        return "https://mabna.shaparak.ir:8080/V1/PeymentApi/Advice"
