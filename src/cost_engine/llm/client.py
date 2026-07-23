"""Structured-output LLM client: schema validation, retry, prompt-version logging.

Every call goes through `structured_call`, which:
  - sends a system + user prompt with a strict JSON schema (output_config.format),
  - validates the response against a pydantic model,
  - retries on transient failure or schema-validation failure,
  - logs the prompt version and model.

The LLM only parses input into the given structured shape. Callers must never
treat any field as a cost or confidence value.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from ..config import CONFIG

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_client = None


def _anthropic():
    global _client
    if _client is None:
        import anthropic  # imported lazily so tests/offline paths don't require it

        if not CONFIG.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Set it in .env, or enable "
                "ALLOW_HEURISTIC_FALLBACK=1 for offline classification only."
            )
        _client = anthropic.Anthropic(api_key=CONFIG.anthropic_api_key)
    return _client


def _schema_for(model: type[BaseModel]) -> dict:
    """JSON schema for structured outputs. Requires additionalProperties: false
    and a required list on every object (structured-output constraint)."""
    schema = model.model_json_schema()
    _strictify(schema)
    return schema


def _strictify(node: object) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"].keys())
        for value in node.values():
            _strictify(value)
    elif isinstance(node, list):
        for item in node:
            _strictify(item)


def structured_call(
    *,
    model: str,
    system: str,
    user: str,
    response_model: type[T],
    prompt_version: str,
    max_retries: int = 3,
    max_tokens: int = 1024,
) -> T:
    """Make one structured LLM call and return a validated pydantic instance."""
    client = _anthropic()
    schema = _schema_for(response_model)
    last_err: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
            if resp.stop_reason == "refusal":
                raise RuntimeError("model refused the request")
            text = next((b.text for b in resp.content if b.type == "text"), "")
            data = json.loads(text)
            instance = response_model.model_validate(data)
            logger.info(
                "llm ok model=%s prompt=%s attempt=%d", model, prompt_version, attempt
            )
            return instance
        except (ValidationError, json.JSONDecodeError, RuntimeError) as e:
            last_err = e
            logger.warning(
                "llm validation/parse failure model=%s prompt=%s attempt=%d: %s",
                model, prompt_version, attempt, e,
            )
        except Exception as e:  # transient API/network errors
            last_err = e
            logger.warning(
                "llm transient failure model=%s prompt=%s attempt=%d: %s",
                model, prompt_version, attempt, e,
            )
        time.sleep(min(2 ** (attempt - 1), 8))

    raise RuntimeError(
        f"structured_call failed after {max_retries} attempts "
        f"(model={model}, prompt={prompt_version}): {last_err}"
    )
