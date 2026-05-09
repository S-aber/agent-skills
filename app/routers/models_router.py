from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["models"])

settings = get_settings()

MODELS = [
    {
        "id": "glm-4-flash",
        "display_name": "GLM-4-Flash (免费)",
        "context_window": 128000,
        "max_output_tokens": 4096,
        "supports_tool_calling": True,
        "is_active": True,
    },
    {
        "id": "glm-4",
        "display_name": "GLM-4",
        "context_window": 128000,
        "max_output_tokens": 4096,
        "supports_tool_calling": True,
        "is_active": True,
    },
    {
        "id": "glm-4-plus",
        "display_name": "GLM-4-Plus",
        "context_window": 128000,
        "max_output_tokens": 4096,
        "supports_tool_calling": True,
        "is_active": True,
    },
]


@router.get("/models")
async def list_models():
    """List available models."""
    return MODELS
