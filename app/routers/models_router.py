from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["models"])

settings = get_settings()

# Pre-configured model list. In production this would come from a database.
MODELS = [
    {
        "id": settings.llm_default_model,
        "display_name": settings.llm_default_model,
        "context_window": 128000,
        "max_output_tokens": 16384,
        "supports_tool_calling": True,
        "is_active": True,
    },
]


@router.get("/models")
async def list_models():
    """List available models."""
    return MODELS
