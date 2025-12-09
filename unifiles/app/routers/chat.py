from typing import Any, AsyncGenerator, List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from unifiles.app.routers.unifiles import get_user_context
from unifiles.core.config.env_config import EnvironmentConfig
from unifiles.core.logging import get_logger

router = APIRouter(prefix="/ai", tags=["AI Chat"])
logger = get_logger()

DEFAULT_MODEL = "gpt-4o-mini"


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = Field(description="Message role")
    content: str = Field(..., min_length=1, description="Message content")


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(
        ..., min_items=1, description="Ordered chat history"
    )
    model: Optional[str] = Field(default=None, description="Chat model to use")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Sampling temp")
    max_tokens: Optional[int] = Field(
        default=None, ge=1, le=4096, description="Max tokens in response"
    )


def _normalize_base_url(url: Optional[str]) -> Optional[str]:
    """Ensure base_url does not duplicate /chat/completions."""
    if not url:
        return None
    suffix = "/chat/completions"
    cleaned = url.rstrip("/")
    if cleaned.endswith(suffix):
        return cleaned[: -len(suffix)]
    return cleaned


def _load_chat_config() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Load base_url, api_key, and default model from environment."""
    env = EnvironmentConfig()
    instances = env.get_api_instances("LANG_LLM")
    base_url = None
    api_key = None
    if instances:
        primary = instances[0]
        base_url = primary.get("url")
        api_key = primary.get("key")

    if not api_key:
        api_key = env.get_env_value("OPENAI_API_KEY", "")

    if not base_url:
        base_url = env.get_env_value("OPENAI_BASE_URL", "") or env.get_env_value(
            "OPENAI_API_BASE", ""
        )

    model = env.get_env_value("UNIFILES_CHAT_DEFAULT_MODEL", "")
    return _normalize_base_url(base_url), api_key, model or None


def _build_openai_client() -> Tuple[AsyncOpenAI, str]:
    """Construct AsyncOpenAI client and default model."""
    base_url, api_key, default_model = _load_chat_config()
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key is not configured")

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    model = default_model or DEFAULT_MODEL
    return AsyncOpenAI(**client_kwargs), model


def _extract_delta_text(delta: Any) -> str:
    """Normalize streaming delta content to plain text."""
    if not delta or not getattr(delta, "content", None):
        return ""

    content = delta.content
    if isinstance(content, str):
        return content

    try:
        return "".join(
            getattr(part, "text", "") for part in content if getattr(part, "text", "")
        )
    except Exception:
        return ""


@router.post(
    "/chat",
    summary="Chat proxy (streaming)",
    response_class=StreamingResponse,
)
async def chat_stream(
    payload: ChatRequest, user_context: dict = Depends(get_user_context)
):
    """Stream chat completions from an OpenAI-compatible backend."""
    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    client, default_model = _build_openai_client()
    model = payload.model or default_model

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            request_kwargs: dict[str, Any] = {
                "model": model,
                "messages": [m.model_dump() for m in payload.messages],
                "temperature": payload.temperature,
                "stream": True,
            }
            if payload.max_tokens is not None:
                request_kwargs["max_tokens"] = payload.max_tokens

            stream = await client.chat.completions.create(**request_kwargs)

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                text = _extract_delta_text(delta)
                if text:
                    yield f"data: {text}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error(f"Chat streaming failed: {exc!s}")
            yield f"data: [ERROR] {exc!s}\n\n"

    logger.info(
        "AI chat stream requested",
        {
            "user_id": user_context.get("user_id"),
            "model": model,
            "message_count": len(payload.messages),
        },
    )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
