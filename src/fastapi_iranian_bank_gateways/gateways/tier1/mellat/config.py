from ....base.config import BaseGatewayConfig


class MellatConfig(BaseGatewayConfig):
    terminal_id: int
    username: str
    password: str

    @property
    def wsdl_url(self) -> str:
        if self.sandbox:
            return "https://bpms.bpi.ir/pgwchannel/services/pgw?wsdl"
        return "https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl"

    @property
    def gateway_url(self) -> str:
        return "https://bpm.shaparak.ir/pgwchannel/startpay.mellat"
