"""Phase 0 entry point: load config, call the provider with a hardcoded prompt, print the reply."""

from __future__ import annotations

import sys

from src.config import load_config
from src.provider import complete

SYSTEM_PROMPT = "You are a concise technical writer. Keep answers under 60 words."
USER_PROMPT = "What is spaced repetition? Answer in 2 sentences."


def main() -> int:
    config = load_config()
    print(f"[orbit] provider check — model = {config.model}")
    print(f"[orbit] active track    — {config.active_track}")
    if config.api_base:
        print(f"[orbit] api_base        — {config.api_base}")
    print()

    reply = complete(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=USER_PROMPT,
        model=config.model,
        api_base=config.api_base,
    )

    print("── LLM response ──")
    print(reply.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
