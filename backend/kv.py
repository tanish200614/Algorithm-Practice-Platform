"""
Small key-value layer: Redis when REDIS_URL is set, local fallbacks otherwise.

Two things use it:
  - the LLM response cache (llm.py), so cached completions are shared by every
    API process and survive a redeploy of the API container;
  - per-user rate limits on the AI endpoints, so a public deployment can't run
    up the OpenAI bill.

Without REDIS_URL the cache falls back to SQLite on disk and the rate limiter
to an in-process dict, which is fine for local development and single-process
deploys. Any Redis works, including a free hosted one (rediss:// URLs for TLS).
"""

import json
import os
import sqlite3
import threading
import time

REDIS_URL = os.environ.get("REDIS_URL", "").strip()
CACHE_TTL_S = int(os.environ.get("LLM_CACHE_TTL_S", str(30 * 24 * 3600)))
SQLITE_PATH = os.environ.get(
    "LLM_CACHE_PATH", os.path.join(os.path.dirname(__file__), "llm_cache.db")
)

_PREFIX = "algobattle:"


class RedisStore:
    name = "redis"

    def __init__(self, client):
        self.r = client

    def get(self, key):
        raw = self.r.get(_PREFIX + "llm:" + key)
        return json.loads(raw) if raw is not None else None

    def put(self, key, value):
        self.r.set(_PREFIX + "llm:" + key, json.dumps(value), ex=CACHE_TTL_S)

    def incr(self, counter):
        self.r.incr(_PREFIX + "stat:" + counter)

    def counters(self):
        keys = ["hits", "misses"]
        vals = self.r.mget([_PREFIX + "stat:" + k for k in keys])
        return {k: int(v or 0) for k, v in zip(keys, vals)}

    def entries(self):
        # SCAN, not KEYS: KEYS blocks the server on a big keyspace.
        return sum(1 for _ in self.r.scan_iter(_PREFIX + "llm:*", count=500))

    def hit_window(self, bucket, window_s):
        """Fixed-window counter. Returns the count after this hit."""
        k = _PREFIX + "rl:" + bucket
        # SET NX starts the window (with its expiry) only if it isn't running,
        # then INCR counts this hit. Works on any Redis version.
        pipe = self.r.pipeline()
        pipe.set(k, 0, ex=window_s, nx=True)
        pipe.incr(k)
        _, count = pipe.execute()
        return int(count)


class LocalStore:
    """SQLite for the cache (survives restarts), memory for counters/limits."""

    name = "sqlite"

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._counters = {"hits": 0, "misses": 0}
        self._windows = {}  # bucket -> (window_start, count)

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.execute(
            "CREATE TABLE IF NOT EXISTS responses ("
            "  key TEXT PRIMARY KEY,"
            "  response TEXT NOT NULL,"
            "  created_at REAL NOT NULL)"
        )
        return c

    def get(self, key):
        c = self._conn()
        row = c.execute(
            "SELECT response, created_at FROM responses WHERE key=?", (key,)
        ).fetchone()
        c.close()
        if not row or time.time() - row[1] > CACHE_TTL_S:
            return None
        return json.loads(row[0])

    def put(self, key, value):
        c = self._conn()
        c.execute(
            "INSERT OR REPLACE INTO responses (key, response, created_at) VALUES (?,?,?)",
            (key, json.dumps(value), time.time()),
        )
        c.commit()
        c.close()

    def incr(self, counter):
        with self._lock:
            self._counters[counter] = self._counters.get(counter, 0) + 1

    def counters(self):
        with self._lock:
            return dict(self._counters)

    def entries(self):
        c = self._conn()
        n = c.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
        c.close()
        return n

    def hit_window(self, bucket, window_s):
        now = time.time()
        with self._lock:
            start, count = self._windows.get(bucket, (now, 0))
            if now - start >= window_s:
                start, count = now, 0
            count += 1
            self._windows[bucket] = (start, count)
            return count


_store = None
_store_lock = threading.Lock()


def store():
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = _make_store()
    return _store


def _make_store():
    if REDIS_URL:
        import redis

        client = redis.Redis.from_url(REDIS_URL, decode_responses=True,
                                      socket_timeout=3, socket_connect_timeout=3)
        try:
            client.ping()
            print(f"[kv] using Redis")
            return RedisStore(client)
        except Exception as e:  # noqa: BLE001 - any connection failure
            # A cache outage shouldn't take the API down with it.
            print(f"[kv] WARNING: Redis unreachable ({e}); falling back to SQLite")
    return LocalStore(SQLITE_PATH)


def set_store(s):
    """For tests."""
    global _store
    _store = s
