"""
OpenAI client with an on-disk response cache.

Generation and interview turns are expensive and, at temperature 0, almost
always repeats: the same problem topic asked twice should not cost twice. Every
call is keyed by its full request — model, messages, tools, schema — so a cache
hit is only ever returned for an identical request.

The key deliberately includes the schema. A generated problem's shape is part
of what was asked for, so changing the schema has to miss the cache rather than
return something built for the old one.
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
    """Raised when no API key is configured, so callers can answer 503 rather
    than 500 — a missing key is a deployment state, not a bug."""


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

    json_schema with strict=True makes the model's output shape a guarantee
    rather than something to defensively parse, which matters here because the
    result is fed straight into a code-execution pipeline.
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
