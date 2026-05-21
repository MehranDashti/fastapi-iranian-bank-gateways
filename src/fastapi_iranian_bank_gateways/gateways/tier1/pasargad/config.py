from ....base.config import BaseGatewayConfig


class PasargadConfig(BaseGatewayConfig):
    username: str
    password: str
    terminal_number: str
    merchant_code: str

    @property
    def token_url(self) -> str:
        return "https://pep.shaparak.ir/Api/v1/Payment/GetToken"

    @property
    def purchase_url(self) -> str:
        return "https://pep.shaparak.ir/Api/v1/Payment/GetUrlAndToken"

    @property
    def check_verify_url(self) -> str:
        return "https://pep.shaparak.ir/Api/v1/Payment/CheckTransactionResult"

    @property
    def verify_url(self) -> str:
        return "https://pep.shaparak.ir/Api/v1/Payment/VerifyPayment"
