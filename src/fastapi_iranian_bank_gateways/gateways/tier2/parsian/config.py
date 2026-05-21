from ....base.config import BaseGatewayConfig


class ParsianConfig(BaseGatewayConfig):
    login_account: str

    @property
    def token_wsdl(self) -> str:
        return "https://pec.shaparak.ir/NewIPGServices/Sale/SaleService.asmx?wsdl"

    @property
    def confirm_wsdl(self) -> str:
        return "https://pec.shaparak.ir/NewIPGServices/Confirm/ConfirmService.asmx?wsdl"

    @property
    def reversal_wsdl(self) -> str:
        return "https://pec.shaparak.ir/NewIPGServices/Reverse/ReversalService.asmx?wsdl"

    @property
    def gateway_url(self) -> str:
        return "https://pec.shaparak.ir/NewIPG/?Token="
