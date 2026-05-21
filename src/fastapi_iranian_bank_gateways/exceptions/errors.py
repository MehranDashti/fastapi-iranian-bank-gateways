from typing import Any


class GatewayError(Exception):
    def __init__(
        self,
        message: str,
        gateway: str | None = None,
        code: str | None = None,
    ) -> None:
        self.gateway = gateway
        self.code = code
        super().__init__(message)


class GatewayConfigurationError(GatewayError):
    """Bad or missing configuration for a gateway."""


class GatewayConnectionError(GatewayError):
    """Network failure communicating with the bank."""


class GatewayAuthError(GatewayError):
    """Token/auth request failed (wrong credentials, expired token, etc.)."""


class GatewayPaymentError(GatewayError):
    """Bank rejected the payment initiation or verification."""

    def __init__(
        self,
        message: str,
        gateway: str | None = None,
        code: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        self.raw: dict[str, Any] = raw or {}
        super().__init__(message, gateway, code)


class MissingDependencyError(GatewayError):
    """Optional dependency (e.g. zeep for SOAP gateways) not installed."""


class OrderNotFoundError(GatewayError):
    """get_order_info callback returned nothing."""


class DuplicatePaymentError(GatewayPaymentError):
    """Payment was already verified (idempotency — treat as success)."""
