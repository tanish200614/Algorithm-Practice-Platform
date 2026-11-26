"""
Role-based access, AI rate limits, and the LLM response cache.

Tokens with a "roles" claim are what the Spring Boot GitHub login service
(auth-service/) mints; they are forged here with the shared key to check this
API honours them.
"""

import time
import types

import jwt
import pytest
from fastapi.testclient import TestClient

import ai_routes
import auth
import kv
import llm


@pytest.fixture()
def store(tmp_path):
    s = kv.LocalStore(str(tmp_path / "cache.db"))
    kv.set_store(s)
    yield s
    kv.set_store(None)


@pytest.fixture()
def client(tmp_path, monkeypatch, store):
    import database

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("llm._client", None)

    import main

    with TestClient(main.app) as c:
        yield c


def github_token(login="octocat", roles=("USER",)):
    """What auth-service issues after a GitHub login."""
    return jwt.encode(
        {"sub": f"gh_{login}", "roles": list(roles), "provider": "github",
         "exp": int(time.time()) + 600},
        auth.SECRET_KEY, algorithm="HS256",
    )


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


class TestRoles:
    def test_password_users_are_plain_users(self, client):
        token = client.post("/api/register",
                            json={"username": "ada", "password": "hunter2"}).json()["token"]
        me = client.get("/api/me", headers=bearer(token)).json()
        assert me["roles"] == ["USER"]
        assert me["provider"] == "password"

    def test_github_tokens_are_accepted_with_their_roles(self, client):
        me = client.get("/api/me", headers=bearer(github_token(roles=["USER", "ADMIN"]))).json()
        assert me["username"] == "gh_octocat"
        assert me["roles"] == ["USER", "ADMIN"]
        assert me["provider"] == "github"

    def test_generation_is_admin_only(self, client):
        res = client.post("/api/ai/generate-problem", json={"topic": "graphs"},
                          headers=bearer(github_token(roles=["USER"])))
        assert res.status_code == 403

    def test_admins_get_past_the_role_check(self, client):
        # 503 (no API key) means it got past RBAC to the model call.
        res = client.post("/api/ai/generate-problem", json={"topic": "graphs"},
                          headers=bearer(github_token(roles=["USER", "ADMIN"])))
        assert res.status_code == 503

    def test_a_forged_role_without_the_key_is_rejected(self, client):
        forged = jwt.encode({"sub": "gh_x", "roles": ["ADMIN"],
                             "exp": int(time.time()) + 600}, "not-the-key", algorithm="HS256")
        res = client.post("/api/ai/generate-problem", json={"topic": "graphs"},
                          headers=bearer(forged))
        assert res.status_code == 401

    def test_github_prefix_is_reserved(self, client):
        res = client.post("/api/register", json={"username": "gh_octocat", "password": "hunter2"})
        assert res.status_code == 400


class TestRateLimit:
    def test_interview_calls_are_limited_per_user(self, client, monkeypatch):
        monkeypatch.setattr(ai_routes, "INTERVIEW_LIMIT_PER_HOUR", 2)
        h = bearer(github_token())
        codes = [client.post("/api/ai/interview", json={"message": "hi"}, headers=h).status_code
                 for _ in range(3)]
        assert codes == [503, 503, 429]

    def test_limits_are_per_user(self, client, monkeypatch):
        monkeypatch.setattr(ai_routes, "INTERVIEW_LIMIT_PER_HOUR", 1)
        client.post("/api/ai/interview", json={"message": "hi"}, headers=bearer(github_token("a")))
        res = client.post("/api/ai/interview", json={"message": "hi"},
                          headers=bearer(github_token("b")))
        assert res.status_code == 503

    def test_window_resets(self, store, monkeypatch):
        assert store.hit_window("x", 60) == 1
        assert store.hit_window("x", 60) == 2
        real = time.time
        monkeypatch.setattr(kv.time, "time", lambda: real() + 61)
        assert store.hit_window("x", 60) == 1


class StubClient:
    def __init__(self):
        self.calls = 0
        self.chat = types.SimpleNamespace(completions=self)

    def create(self, **_):
        self.calls += 1
        msg = types.SimpleNamespace(content='{"answer": 42}')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


class TestCache:
    SCHEMA = {"type": "object", "properties": {"answer": {"type": "integer"}}}

    def test_repeat_requests_are_served_from_cache(self, store, monkeypatch):
        stub = StubClient()
        monkeypatch.setattr(llm, "get_client", lambda: stub)
        msgs = [{"role": "user", "content": "q"}]
        for _ in range(4):
            assert llm.structured(msgs, self.SCHEMA, "t") == {"answer": 42}
        assert stub.calls == 1
        stats = llm.cache_stats()
        assert (stats["hits"], stats["misses"], stats["hit_rate"]) == (3, 1, 0.75)

    def test_use_cache_false_always_calls_the_api(self, store, monkeypatch):
        stub = StubClient()
        monkeypatch.setattr(llm, "get_client", lambda: stub)
        msgs = [{"role": "user", "content": "q"}]
        llm.structured(msgs, self.SCHEMA, "t")
        llm.structured(msgs, self.SCHEMA, "t", use_cache=False)
        assert stub.calls == 2


class TestRedisStore:
    """Same behaviour against a Redis implementation (fakeredis, in-process)."""

    @pytest.fixture()
    def rstore(self):
        fakeredis = pytest.importorskip("fakeredis")
        return kv.RedisStore(fakeredis.FakeRedis(decode_responses=True))

    def test_roundtrip_and_counters(self, rstore):
        assert rstore.get("k") is None
        rstore.put("k", {"a": [1, 2]})
        assert rstore.get("k") == {"a": [1, 2]}
        rstore.incr("hits")
        rstore.incr("misses")
        rstore.incr("hits")
        assert rstore.counters() == {"hits": 2, "misses": 1}
        assert rstore.entries() == 1

    def test_cache_entries_expire(self, rstore):
        rstore.put("k", 1)
        assert 0 < rstore.r.ttl("algobattle:llm:k") <= kv.CACHE_TTL_S

    def test_rate_window(self, rstore):
        assert [rstore.hit_window("u", 60) for _ in range(3)] == [1, 2, 3]
        assert 0 < rstore.r.ttl("algobattle:rl:u") <= 60
