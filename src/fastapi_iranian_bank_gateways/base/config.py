from pydantic import BaseModel, Field


class BaseGatewayConfig(BaseModel):
    model_config = {"frozen": True}

    sandbox: bool = False
    timeout: float = Field(default=30.0, gt=0)
