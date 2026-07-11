import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A client backed by a throwaway database, so tests never touch the
    developer's real ratings."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))

    import database

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))

    import main

    with TestClient(main.app) as c:
        yield c


def register(client, username="ada", password="hunter2"):
    return client.post("/api/register", json={"username": username, "password": password})


class TestAuth:
    def test_register_then_login(self, client):
        assert register(client).status_code == 200
        res = client.post("/api/login", json={"username": "ada", "password": "hunter2"})
        assert res.status_code == 200
        assert res.json()["username"] == "ada"

    def test_duplicate_username_is_rejected(self, client):
        register(client)
        assert register(client).status_code == 409

    @pytest.mark.parametrize("username", ["ab", "has spaces", "way_too_long_username_here", "sql'inject"])
    def test_invalid_usernames_are_rejected(self, client, username):
        assert register(client, username=username).status_code == 400

    def test_short_passwords_are_rejected(self, client):
        assert register(client, password="123").status_code == 400

    def test_wrong_password_is_rejected(self, client):
        register(client)
        res = client.post("/api/login", json={"username": "ada", "password": "wrong"})
        assert res.status_code == 401

    def test_me_requires_a_token(self, client):
        assert client.get("/api/me").status_code == 401

    def test_me_rejects_a_forged_token(self, client):
        res = client.get("/api/me", headers={"Authorization": "Bearer not.a.token"})
        assert res.status_code == 401

    def test_me_returns_the_players_standing(self, client):
        token = register(client).json()["token"]
        body = client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).json()
        assert body["username"] == "ada"
        assert body["skill"] == 1000
        assert "recommendation" in body


class TestMetadata:
    def test_health_reports_the_sandbox_mode(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert "sandbox" in body

    def test_problems_carry_a_difficulty(self, client):
        problems = client.get("/api/problems").json()
        assert len(problems) >= 3
        for p in problems:
            assert p["tier"] in {"Easy", "Medium", "Hard"}
            assert 1 <= p["score"] <= 10

    def test_all_three_languages_are_offered(self, client):
        ids = {lang["id"] for lang in client.get("/api/languages").json()}
        assert ids == {"python", "cpp", "java"}

    def test_leaderboard_lists_registered_players(self, client):
        register(client)
        names = [row["name"] for row in client.get("/api/leaderboard").json()]
        assert "ada" in names

    def test_sandbox_status_states_whether_it_isolates(self, client):
        from sandbox import SANDBOX_MODES

        body = client.get("/api/sandbox").json()
        assert isinstance(body["isolated"], bool)
        # Compared against the module's own set rather than a copy, so adding a
        # mode cannot leave this assertion silently stale.
        assert body["mode"] in SANDBOX_MODES
        # Whatever the mode, the per-language breakdown has to be complete.
        assert set(body["languages"]) == {"python", "cpp", "java"}


class TestExecution:
    def test_running_python_returns_output_and_limits(self, client):
        res = client.post("/api/run", json={"code": "print(6*7)", "language": "python"})
        body = res.json()
        assert body["stdout"].strip() == "42"
        assert body["memory_limit_mb"] > 0
        assert body["time_limit_s"] > 0

    def test_an_unsupported_language_is_rejected(self, client):
        res = client.post("/api/run", json={"code": "puts 1", "language": "ruby"})
        assert res.status_code == 400


class TestRooms:
    def test_creating_a_room_returns_a_code_and_problem(self, client):
        res = client.post("/api/room/create", json={"problem_id": "two_sum"})
        body = res.json()
        assert len(body["room_code"]) == 6
        assert body["problem"]["id"] == "two_sum"

    def test_fetching_an_unknown_room_reports_an_error(self, client):
        assert "error" in client.get("/api/room/ZZZZZZ").json()

    def test_a_created_room_can_be_fetched(self, client):
        code = client.post("/api/room/create", json={"problem_id": "two_sum"}).json()["room_code"]
        body = client.get(f"/api/room/{code}").json()
        assert body["status"] == "waiting"
        assert body["player_count"] == 0


class TestRatingPersistence:
    """ELO rates players against problems. Persisting one side without the
    other lets the two drift apart across restarts."""

    def test_problem_difficulty_survives_a_restart(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
        import database
        monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "t.db"))
        database.init_db()

        from ml import EloTracker

        # A first run where everyone fails the problem, so it rates upward.
        hot = EloTracker()
        for i in range(30):
            hot.update(f"p{i}", "two_sum", solved=False)
        drifted = hot.get_difficulty("two_sum")
        assert drifted > 1200
        database.upsert_problem_stats(
            "two_sum", drifted, hot.get_attempts("two_sum")
        )

        # A second process starts with a fresh tracker and reloads.
        cold = EloTracker()
        assert cold.get_difficulty("two_sum") == 1000      # before restoring
        for row in database.all_problem_stats():
            cold._difficulties[row["problem_id"]] = row["difficulty"]
            cold._attempts[row["problem_id"]] = row["attempts"]

        assert cold.get_difficulty("two_sum") == drifted
        assert cold.get_attempts("two_sum") == 30

    def test_a_problem_never_played_keeps_its_seeded_difficulty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
        import database
        monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "t.db"))
        database.init_db()
        assert database.all_problem_stats() == []
