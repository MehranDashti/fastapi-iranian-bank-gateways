from enum import Enum


class PaymentStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PENDING = "pending"
    DUPLICATE = "duplicate"


class Currency(str, Enum):
    IRR = "IRR"  # Rials
    IRT = "IRT"  # Tomans (= IRR / 10)


class GatewayType(str, Enum):
    REST = "rest"
    SOAP = "soap"
