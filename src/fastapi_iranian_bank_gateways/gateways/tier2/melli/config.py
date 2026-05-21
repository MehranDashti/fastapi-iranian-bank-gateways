from ....base.config import BaseGatewayConfig


class MelliConfig(BaseGatewayConfig):
    terminal_id: str
    merchant_id: str

    @property
    def token_url(self) -> str:
        if self.sandbox:
            return "https://bpms.bpi.ir/pgwchannel/services/rest/PaymentTokenRequest"
        return "https://bpm.shaparak.ir/pgwchannel/services/rest/PaymentTokenRequest"

    @property
    def gateway_url(self) -> str:
        if self.sandbox:
            return "https://bpms.bpi.ir/pgwchannel/startpay.mellat"
        return "https://bpm.shaparak.ir/pgwchannel/startpay.mellat"

    @property
    def verify_url(self) -> str:
        if self.sandbox:
            return "https://bpms.bpi.ir/pgwchannel/services/rest/VerifyPayment"
        return "https://bpm.shaparak.ir/pgwchannel/services/rest/VerifyPayment"
