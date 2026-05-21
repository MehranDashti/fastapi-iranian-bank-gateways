from unittest.mock import MagicMock, patch

import pytest

from fastapi_iranian_bank_gateways.exceptions import GatewayPaymentError
from fastapi_iranian_bank_gateways.gateways.tier2.parsian import ParsianConfig, ParsianGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

SOAP_PATH = "fastapi_iranian_bank_gateways.gateways.tier2.parsian.gateway.get_soap_client"


@pytest.fixture
def gateway():
    return ParsianGateway(ParsianConfig(login_account="PARSIAN-ACC"))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="12345",
        amount=180000,
        callback_url="https://shop.com/payments/parsian/verify",
    )


@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    mock_client = MagicMock()
    mock_client.service.SalePaymentRequest.return_value = {"Status": 0, "Token": 987654}
    with patch(SOAP_PATH, return_value=mock_client):
        result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "987654" in result.url


@pytest.mark.asyncio
async def test_initiate_failure(gateway, payment_request):
    mock_client = MagicMock()
    mock_client.service.SalePaymentRequest.return_value = {"Status": -1, "Token": -1}
    with patch(SOAP_PATH, return_value=mock_client):
        with pytest.raises(GatewayPaymentError):
            await gateway.initiate(payment_request)


@pytest.mark.asyncio
async def test_verify_success(gateway):
    mock_client = MagicMock()
    mock_client.service.ConfirmPayment.return_value = {"Status": 0, "RRN": "RRN-PAR-001"}
    with patch(SOAP_PATH, return_value=mock_client):
        callback = BankCallbackData(
            gateway_slug="parsian",
            raw={
                "Token": "987654",
                "status": "0",
                "OrderId": "12345",
                "RRN": "RRN-PAR-001",
            },
        )
        result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "RRN-PAR-001"


@pytest.mark.asyncio
async def test_verify_failed_callback_status(gateway):
    callback = BankCallbackData(
        gateway_slug="parsian",
        raw={"Token": "987654", "status": "-1", "OrderId": "12345"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED


@pytest.mark.asyncio
async def test_verify_failed_confirm(gateway):
    mock_client = MagicMock()
    mock_client.service.ConfirmPayment.return_value = {"Status": -2}
    with patch(SOAP_PATH, return_value=mock_client):
        callback = BankCallbackData(
            gateway_slug="parsian",
            raw={"Token": "987654", "status": "0", "OrderId": "12345"},
        )
        result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "-2"
