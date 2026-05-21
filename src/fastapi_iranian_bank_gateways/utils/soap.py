from typing import Any

from ..exceptions.errors import MissingDependencyError


def get_soap_client(wsdl_url: str) -> Any:
    """
    Lazily import zeep. Raises MissingDependencyError with install hint if not installed.
    Install SOAP support: pip install "fastapi-iranian-bank-gateways[soap]"
    """
    try:
        import zeep  # type: ignore
    except ImportError:
        raise MissingDependencyError(
            "zeep is required for SOAP-based gateways (Mellat, Sepah, Parsian). "
            'Install it with: pip install "fastapi-iranian-bank-gateways[soap]"',
            gateway=None,
        )
    return zeep.Client(wsdl=wsdl_url)  # type: ignore
