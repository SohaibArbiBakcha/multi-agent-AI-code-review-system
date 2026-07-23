"""Thin wrapper around the local Ollama HTTP API.

All LLM calls in CodeSentinel go through this module so that model names,
timeouts and JSON-extraction/retry logic live in exactly one place.
"""
import json
import os
import re

import ollama
from loguru import logger

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CODE_MODEL = os.getenv("OLLAMA_CODE_MODEL", "qwen2.5-coder:7b")
REPORT_MODEL = os.getenv("OLLAMA_REPORT_MODEL", "mistral:7b")

_client = ollama.Client(host=OLLAMA_HOST)


class OllamaUnavailableError(RuntimeError):
    """Raised when the local Ollama server cannot be reached."""


def _extract_json(text: str):
    """Pull the first well-formed JSON object/array out of a model reply.

    Models occasionally wrap JSON in prose or markdown fences despite
    instructions; this salvages the payload instead of failing outright.
    """
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = fence.group(1) if fence else text
    start = min(
        (i for i in (candidate.find("["), candidate.find("{")) if i != -1),
        default=-1,
    )
    if start == -1:
        raise ValueError("No JSON object found in model output")
    depth = 0
    opening = candidate[start]
    closing = "]" if opening == "[" else "}"
    for i, ch in enumerate(candidate[start:], start=start):
        if ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return json.loads(candidate[start : i + 1])
    raise ValueError("Unbalanced JSON in model output")


def generate_json(prompt: str, system: str, model: str = CODE_MODEL, retries: int = 2):
    """Call the model and parse a JSON reply, retrying once on malformed output."""
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = _client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.1},
            )
            content = response["message"]["content"]
            return _extract_json(content)
        except (ollama.ResponseError, ConnectionError) as exc:
            raise OllamaUnavailableError(
                f"Could not reach Ollama at {OLLAMA_HOST}: {exc}"
            ) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.warning(f"JSON parse failed (attempt {attempt + 1}): {exc}")
    raise ValueError(f"Model did not return valid JSON after {retries + 1} attempts: {last_error}")


def generate_text(prompt: str, system: str, model: str = REPORT_MODEL) -> str:
    """Call the model and return raw text (used for the Markdown report)."""
    try:
        response = _client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.3},
        )
        return response["message"]["content"]
    except (ollama.ResponseError, ConnectionError) as exc:
        raise OllamaUnavailableError(
            f"Could not reach Ollama at {OLLAMA_HOST}: {exc}"
        ) from exc
