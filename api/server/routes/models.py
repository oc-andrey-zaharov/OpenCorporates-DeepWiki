"""Routes related to provider/model configuration."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.config import configs

logger = logging.getLogger(__name__)


class Model(BaseModel):
    """LLM model metadata exposed via the API."""

    id: str = Field(..., description="Model identifier")
    name: str = Field(..., description="Display name for the model")


class Provider(BaseModel):
    """Provider metadata that includes the available models."""

    id: str = Field(..., description="Provider identifier")
    name: str = Field(..., description="Display name for the provider")
    models: list[Model] = Field(
        ..., description="List of available models for this provider",
    )
    supportsCustomModel: bool | None = Field(
        False, description="Whether this provider supports custom models",
    )


class ModelConfig(BaseModel):
    """Complete model configuration payload returned to clients."""

    providers: list[Provider] = Field(
        ..., description="List of available model providers",
    )
    defaultProvider: str = Field(..., description="ID of the default provider")


router = APIRouter(prefix="/models", tags=["models"])


@router.get("/config", response_model=ModelConfig)
async def get_model_config():
    """Return available model providers and their models."""
    try:
        providers: list[Provider] = []
        default_provider = configs.get("default_provider", "google")

        for provider_id, provider_config in configs["providers"].items():
            models = [
                Model(id=model_id, name=model_id)
                for model_id in provider_config["models"].keys()
            ]
            providers.append(
                Provider(
                    id=provider_id,
                    name=provider_id.capitalize(),
                    supportsCustomModel=provider_config.get("supportsCustomModel", False),
                    models=models,
                ),
            )

        return ModelConfig(providers=providers, defaultProvider=default_provider)

    except Exception as exc:
        logger.error("Error creating model configuration: %s", exc)
        return ModelConfig(
            providers=[
                Provider(
                    id="google",
                    name="Google",
                    supportsCustomModel=True,
                    models=[Model(id="gemini-2.5-flash", name="Gemini 2.5 Flash")],
                ),
            ],
            defaultProvider="google",
        )


__all__ = ["ModelConfig", "router"]
