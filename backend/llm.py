"""
OpenAI client with a response cache (Redis, or SQLite when Redis is not set).

Generation and interview calls are expensive and mostly repeat at temperature
0, so responses are cached. The key is the full request (model, messages,
tools, schema), so changing the schema also misses the cache.
"""

import hashlib
import json
import os

import kv

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

_client = None


class LLMUnavailable(RuntimeError):
    """Raised when no API key is set, so callers can return 503 instead of 500."""


def get_client():
    global _client
    if _client is None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise LLMUnavailable("OPENAI_API_KEY is not set")
        from openai import OpenAI

        _client = OpenAI(api_key=key)
    return _client


# ── Cache ─────────────────────────────────────────────────────────────────────
# Stored in Redis when REDIS_URL is set, SQLite otherwise (see kv.py). Hits and
# misses are counted so the saving is a measured number, not a guess.

def cache_key(payload: dict) -> str:
    # sort_keys so dict ordering never produces two keys for one request.
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


def cache_get(key: str):
    return kv.store().get(key)


def cache_put(key: str, value):
    kv.store().put(key, value)


def cache_stats() -> dict:
    s = kv.store()
    c = s.counters()
    total = c["hits"] + c["misses"]
    return {
        "backend": s.name,
        "entries": s.entries(),
        "hits": c["hits"],
        "misses": c["misses"],
        # Fraction of requests answered without calling the API.
        "hit_rate": round(c["hits"] / total, 3) if total else None,
    }


# ── Structured completion ─────────────────────────────────────────────────────

def structured(messages: list, schema: dict, name: str, model: str = None,
               temperature: float = 0.0, use_cache: bool = True) -> dict:
    """
    One completion constrained to `schema`, returned as a dict.

    strict=True guarantees the output shape, which matters since the result
    goes straight into code execution.
    """
    model = model or MODEL
    request = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": name, "schema": schema, "strict": True},
        },
    }

    key = cache_key(request)
    if use_cache:
        hit = cache_get(key)
        if hit is not None:
            kv.store().incr("hits")
            return hit
        kv.store().incr("misses")

    completion = get_client().chat.completions.create(**request)
    parsed = json.loads(completion.choices[0].message.content)
    cache_put(key, parsed)
    return parsed
