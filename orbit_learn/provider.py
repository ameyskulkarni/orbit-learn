"""The ONLY module that touches LiteLLM. All LLM calls in Orbit flow through `complete()`."""

from __future__ import annotations

import litellm


def complete(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 4000,
    response_format: dict | None = None,
    api_base: str | None = None,
) -> str:
    """Single entry point for all LLM calls. Returns the text response.

    The `model` string is a LiteLLM identifier like "anthropic/claude-sonnet-4-5",
    "openai/gpt-4o", or "ollama/llama3.1:8b". The corresponding API key (for hosted
    providers) must be set in the environment (see .env.example). `api_base` overrides
    the endpoint — used for Ollama, LM Studio, or any OpenAI-compatible local server.
    No other file in the codebase should import litellm.
    """
    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if api_base is not None:
        kwargs["api_base"] = api_base

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content
