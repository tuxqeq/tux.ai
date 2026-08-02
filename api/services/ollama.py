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

    Strips Qwen3 <think>...</think> reasoning blocks before yielding.
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

            in_think = False
            think_buf = ""

            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                content = data.get("message", {}).get("content", "")
                if content:
                    # Buffer and strip <think>...</think> blocks (Qwen3 reasoning)
                    think_buf += content
                    while True:
                        if in_think:
                            end = think_buf.find("</think>")
                            if end == -1:
                                think_buf = ""  # still inside think block, discard
                                break
                            think_buf = think_buf[end + len("</think>"):]
                            in_think = False
                        else:
                            start = think_buf.find("<think>")
                            if start == -1:
                                if think_buf:
                                    yield think_buf
                                think_buf = ""
                                break
                            if start > 0:
                                yield think_buf[:start]
                            think_buf = think_buf[start + len("<think>"):]
                            in_think = True

                if data.get("done"):
                    if think_buf and not in_think:
                        yield think_buf
                    break
