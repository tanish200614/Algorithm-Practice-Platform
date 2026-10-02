"""
OpenAI client with an on-disk response cache.

Generation and interview calls are expensive and mostly repeat at temperature
0, so responses are cached. The key is the full request (model, messages,
tools, schema), so changing the schema also misses the cache.
"""

import hashlib
import json
import os
import sqlite3
import time

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
CACHE_PATH = os.environ.get(
    "LLM_CACHE_PATH", os.path.join(os.path.dirname(__file__), "llm_cache.db")
)

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

def _cache_conn():
    c = sqlite3.connect(CACHE_PATH)
    c.execute(
        "CREATE TABLE IF NOT EXISTS responses ("
        "  key TEXT PRIMARY KEY,"
        "  response TEXT NOT NULL,"
        "  created_at REAL NOT NULL)"
    )
    return c


def cache_key(payload: dict) -> str:
    # sort_keys so dict ordering never produces two keys for one request.
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


def cache_get(key: str):
    c = _cache_conn()
    row = c.execute("SELECT response FROM responses WHERE key=?", (key,)).fetchone()
    c.close()
    return json.loads(row[0]) if row else None


def cache_put(key: str, value):
    c = _cache_conn()
    c.execute(
        "INSERT OR REPLACE INTO responses (key, response, created_at) VALUES (?,?,?)",
        (key, json.dumps(value), time.time()),
    )
    c.commit()
    c.close()


def cache_stats() -> dict:
    c = _cache_conn()
    n = c.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
    c.close()
    return {"entries": n, "path": CACHE_PATH}


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
            return hit

    completion = get_client().chat.completions.create(**request)
    parsed = json.loads(completion.choices[0].message.content)
    cache_put(key, parsed)
    return parsed
