import pytest

from fastapi_iranian_bank_gateways.exceptions import (
    GatewayConnectionError,
    GatewayError,
    GatewayPaymentError,
    MissingDependencyError,
)


def test_gateway_error_hierarchy():
    err = GatewayConnectionError("Network error", gateway="mellat")
    assert isinstance(err, GatewayError)
    assert err.gateway == "mellat"
    assert str(err) == "Network error"


def test_payment_error_raw():
    err = GatewayPaymentError("Rejected", gateway="zarinpal", code="-9", raw={"x": 1})
    assert err.code == "-9"
    assert err.raw == {"x": 1}


def test_missing_dependency_error():
    err = MissingDependencyError(
        'Install with: pip install "fastapi-iranian-bank-gateways[soap]"'
    )
    assert "soap" in str(err)
    assert isinstance(err, GatewayError)


def test_soap_util_raises_missing_dependency(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "zeep":
            raise ImportError("No module named 'zeep'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from fastapi_iranian_bank_gateways.utils.soap import get_soap_client
    with pytest.raises(MissingDependencyError) as exc_info:
        get_soap_client("https://example.com/wsdl")
    assert "soap" in str(exc_info.value).lower()
