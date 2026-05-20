"""
Async Ollama chat client with streaming.
Yields text chunks as they arrive from the model.
"""
import json
from typing import AsyncIterator, List

import httpx

from api.config import get_settings


async def stream_chat(
    messages: List[dict],
    model: str | None = None,
) -> AsyncIterator[str]:
    """
    Stream chat completions from Ollama.

    Each yielded value is a text delta string (may be empty for the final done message).
    Raises httpx.HTTPError on connection failure.
    """
    settings = get_settings()
    url = f"{settings.OLLAMA_URL}/api/chat"
    payload = {
        "model": model or settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                content = data.get("message", {}).get("content", "")
                if content:
                    yield content

                if data.get("done"):
                    break
