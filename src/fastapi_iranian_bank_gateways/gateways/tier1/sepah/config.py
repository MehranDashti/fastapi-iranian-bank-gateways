from ....base.config import BaseGatewayConfig


class SepahConfig(BaseGatewayConfig):
    login_account: str

    @property
    def wsdl_url(self) -> str:
        return "https://sepehr.shaparak.ir:8081/ws/MerchantService?wsdl"

    @property
    def gateway_redirect_url(self) -> str:
        return "https://sepehr.shaparak.ir:8080/Pay?Token="
