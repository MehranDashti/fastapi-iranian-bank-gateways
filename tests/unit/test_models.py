import pytest
from pydantic import ValidationError

from fastapi_iranian_bank_gateways.models.callback import PaymentResult
from fastapi_iranian_bank_gateways.models.enums import Currency, PaymentStatus
from fastapi_iranian_bank_gateways.models.payment import PaymentRequest


def test_payment_request_valid():
    req = PaymentRequest(
        order_id="ORDER-001",
        amount=100000,
        callback_url="https://shop.com/verify",
        mobile="09123456789",
    )
    assert req.order_id == "ORDER-001"
    assert req.amount == 100000
    assert req.currency == Currency.IRR


def test_payment_request_requires_positive_amount():
    with pytest.raises(ValidationError):
        PaymentRequest(
            order_id="ORDER-001",
            amount=0,
            callback_url="https://shop.com/verify",
        )


def test_payment_result_success():
    result = PaymentResult(
        status=PaymentStatus.SUCCESS,
        gateway_slug="zarinpal",
        order_id="ORDER-001",
        reference_id="REF-123",
    )
    assert result.status == PaymentStatus.SUCCESS
    assert result.raw_response == {}


def test_payment_result_failed():
    result = PaymentResult(
        status=PaymentStatus.FAILED,
        gateway_slug="mellat",
        order_id="ORDER-001",
        error_code="21",
    )
    assert result.status == PaymentStatus.FAILED
    assert result.error_code == "21"
