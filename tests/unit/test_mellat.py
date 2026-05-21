from unittest.mock import MagicMock, patch

import pytest

from fastapi_iranian_bank_gateways.exceptions import GatewayPaymentError
from fastapi_iranian_bank_gateways.gateways.tier1.mellat import MellatConfig, MellatGateway
from fastapi_iranian_bank_gateways.models.callback import BankCallbackData
from fastapi_iranian_bank_gateways.models.enums import PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest

SOAP_PATH = "fastapi_iranian_bank_gateways.gateways.tier1.mellat.gateway.get_soap_client"


@pytest.fixture
def gateway():
    return MellatGateway(MellatConfig(
        terminal_id=12345678,
        username="user",
        password="pass",
        sandbox=True,
    ))


@pytest.fixture
def payment_request():
    return PaymentRequest(
        order_id="ORDER-MEL-001",
        amount=100000,
        callback_url="https://shop.com/payments/mellat/verify",
    )


@pytest.mark.asyncio
async def test_initiate_success(gateway, payment_request):
    mock_client = MagicMock()
    mock_client.service.bpPayRequest.return_value = "0,REF123456"
    with patch(SOAP_PATH, return_value=mock_client):
        result = await gateway.initiate(payment_request)
    assert result.type == "form"
    assert "REF123456" in result.html


@pytest.mark.asyncio
async def test_initiate_failure_non_zero_code(gateway, payment_request):
    mock_client = MagicMock()
    mock_client.service.bpPayRequest.return_value = "21,something"
    with patch(SOAP_PATH, return_value=mock_client):
        with pytest.raises(GatewayPaymentError) as exc_info:
            await gateway.initiate(payment_request)
    assert exc_info.value.code == "21"


@pytest.mark.asyncio
async def test_verify_success(gateway):
    mock_client = MagicMock()
    mock_client.service.bpVerifyRequest.return_value = "0"
    with patch(SOAP_PATH, return_value=mock_client):
        callback = BankCallbackData(
            gateway_slug="mellat",
            raw={
                "ResCode": "0",
                "SaleOrderId": "ORDER-MEL-001",
                "SaleReferenceId": "REF123456",
            },
        )
        result = await gateway.verify(callback)
    assert result.status == PaymentStatus.SUCCESS
    assert result.reference_id == "REF123456"


@pytest.mark.asyncio
async def test_verify_duplicate(gateway):
    mock_client = MagicMock()
    mock_client.service.bpVerifyRequest.return_value = "43"
    with patch(SOAP_PATH, return_value=mock_client):
        callback = BankCallbackData(
            gateway_slug="mellat",
            raw={
                "ResCode": "0",
                "SaleOrderId": "ORDER-MEL-001",
                "SaleReferenceId": "REF123456",
            },
        )
        result = await gateway.verify(callback)
    assert result.status == PaymentStatus.DUPLICATE


@pytest.mark.asyncio
async def test_verify_failed_callback_rescode(gateway):
    callback = BankCallbackData(
        gateway_slug="mellat",
        raw={"ResCode": "21", "SaleOrderId": "ORDER-MEL-001"},
    )
    # No SOAP call made when ResCode is not 0 or 43
    result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "21"


@pytest.mark.asyncio
async def test_verify_failed_soap_response(gateway):
    mock_client = MagicMock()
    mock_client.service.bpVerifyRequest.return_value = "55"
    with patch(SOAP_PATH, return_value=mock_client):
        callback = BankCallbackData(
            gateway_slug="mellat",
            raw={
                "ResCode": "0",
                "SaleOrderId": "ORDER-MEL-001",
                "SaleReferenceId": "REF123456",
            },
        )
        result = await gateway.verify(callback)
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "55"
