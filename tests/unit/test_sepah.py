from unittest.mock import MagicMock, patch

import pytest

from fastapi_iranian_bank_gateways.exceptions import GatewayPaymentError
from fastapi_iranian_bank_gateways.gateways.tier1.sepah import SepahConfig, SepahGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

SOAP_PATH = "fastapi_iranian_bank_gateways.gateways.tier1.sepah.gateway.get_soap_client"


@pytest.fixture
def gateway():
    return SepahGateway(SepahConfig(login_account="SEPAH-ACCOUNT"))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-SEP-001",
        amount=250000,
        callback_url="https://shop.com/payments/sepah/verify",
    )


@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    mock_client = MagicMock()
    mock_client.service.SalePaymentRequest.return_value = {"Status": 0, "Token": "SEPAH-TOKEN"}
    with patch(SOAP_PATH, return_value=mock_client):
        result = await gateway.initiate(payment_request)
    assert result.type == "redirect"
    assert "SEPAH-TOKEN" in result.url


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
    mock_client.service.ConfirmPayment.return_value = {
        "Status": 0,
        "RRN": "RRN-001",
        "CardNumberMasked": "6037****1234",
    }
    with patch(SOAP_PATH, return_value=mock_client):
        callback = BankCallbackData(
            gateway_slug="sepah",
            raw={"status": "1", "OrderId": "ORDER-SEP-001", "Token": "SEPAH-TOKEN"},
        )
        result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "RRN-001"


@pytest.mark.asyncio
async def test_verify_failed_callback_status(gateway):
    callback = BankCallbackData(
        gateway_slug="sepah",
        raw={"status": "0", "OrderId": "ORDER-SEP-001", "Token": "SEPAH-TOKEN"},
    )
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "0"


@pytest.mark.asyncio
async def test_verify_failed_confirm(gateway):
    mock_client = MagicMock()
    mock_client.service.ConfirmPayment.return_value = {"Status": -1}
    with patch(SOAP_PATH, return_value=mock_client):
        callback = BankCallbackData(
            gateway_slug="sepah",
            raw={"status": "1", "OrderId": "ORDER-SEP-001", "Token": "SEPAH-TOKEN"},
        )
        result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
