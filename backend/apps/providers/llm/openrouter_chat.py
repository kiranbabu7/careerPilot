"""Shared LangChain OpenRouter chat client."""

from __future__ import annotations

from django.conf import settings
from langchain_openai import ChatOpenAI

DEFAULT_OPENROUTER_MODEL = "google/gemini-2.5-flash"


def get_openrouter_chat(
    *,
    model: str | None = None,
    temperature: float = 0.2,
    timeout: int = 90,
    response_format: dict | None = None,
) -> ChatOpenAI:
    """Return a ChatOpenAI client configured for OpenRouter."""
    kwargs: dict = {
        "model": model or DEFAULT_OPENROUTER_MODEL,
        "api_key": settings.OPENAI_API_KEY,
        "base_url": settings.OPENROUTER_BASE_URL.rstrip("/"),
        "temperature": temperature,
        "timeout": timeout,
    }
    if response_format is not None:
        kwargs["model_kwargs"] = {"response_format": response_format}
    return ChatOpenAI(**kwargs)


def invoke_openrouter(prompt_text: str, *, model: str | None = None, **kwargs) -> str:
    """Invoke OpenRouter and return stripped text content."""
    client = get_openrouter_chat(model=model, **kwargs)
    response = client.invoke(prompt_text)
    content = response.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts).strip()
    return str(content).strip()


def openrouter_configured() -> bool:
    return bool(getattr(settings, "OPENAI_API_KEY", "") and getattr(settings, "OPENROUTER_BASE_URL", ""))
