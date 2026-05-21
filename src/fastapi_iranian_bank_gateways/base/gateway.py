from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from ..models.callback import BankCallbackData, PaymentResult
from ..models.payment import InitiateResponse, PaymentRequest
from .config import BaseGatewayConfig

if TYPE_CHECKING:
    from ..adapters import HttpTransportAdapter


class AbstractGateway(ABC):
    """
    Base class for all Iranian payment gateways.

    Subclasses must declare:
      gateway_slug  — unique lowercase identifier ("mellat", "zarinpal", etc.)
      config_class  — the Pydantic config model class
      callback_method — "GET" or "POST" (which HTTP method the bank uses for callbacks)

    Optionally accept a ``transport`` (HttpTransportAdapter) to override the
    default httpx-based HTTP client.  Useful for connection pooling or injecting
    a test double without needing respx.
    """

    gateway_slug: ClassVar[str]
    config_class: ClassVar[type[BaseGatewayConfig]]
    callback_method: ClassVar[str] = "POST"

    def __init__(
        self,
        config: BaseGatewayConfig,
        transport: HttpTransportAdapter | None = None,
    ) -> None:
        self.config = config
        # Transport is stored but gateways that haven't migrated yet ignore it.
        # Gateways that opt-in (e.g. ZarinpalGateway, IDPayGateway) use
        # self.transport.post() / self.transport.get() instead of httpx directly.
        if transport is not None:
            self.transport: HttpTransportAdapter = transport
        else:
            from ..adapters import HttpxAdapter
            self.transport = HttpxAdapter(gateway=self.gateway_slug)

    @abstractmethod
    async def initiate(self, request: PaymentRequest) -> InitiateResponse:
        """
        Start a payment.
        Returns FormInitiateResponse (HTML auto-submit) or RedirectInitiateResponse (302 URL).
        """
        ...

    @abstractmethod
    async def verify(self, callback_data: BankCallbackData) -> PaymentResult:
        """
        Verify/confirm a payment after the bank redirects back.
        Called by GatewayManager when the bank posts to the verify endpoint.
        """
        ...

    def parse_callback(self, request_data: dict[str, Any]) -> BankCallbackData:
        """
        Parse raw query/form params into BankCallbackData.
        Override in gateways that need special parsing (e.g. XML body).
        """
        return BankCallbackData(
            gateway_slug=self.gateway_slug,
            raw=request_data,
        )
