import sqlite3, os

# Overridable so a deployment can point the database at a mounted volume;
# otherwise it would live in the image layer and be lost on every redeploy.
DB_PATH = os.environ.get("DB_PATH") or os.path.join(os.path.dirname(__file__), "algobattle.db")


def _conn():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS player_stats (
            username TEXT PRIMARY KEY,
            skill    REAL    DEFAULT 1000,
            solves   INTEGER DEFAULT 0
        );
        -- The other half of the ELO pair. Without it, restarts kept the
        -- ratings players earned but reset the difficulties they were earned
        -- against, so the two sides of the system drifted apart.
        CREATE TABLE IF NOT EXISTS problem_stats (
            problem_id TEXT PRIMARY KEY,
            difficulty REAL    DEFAULT 1000,
            attempts   INTEGER DEFAULT 0
        );
    """)
    c.commit()
    c.close()


# ── Users ──────────────────────────────────────────────────────────────────────

def create_user(username: str, password_hash: str) -> bool:
    try:
        c = _conn()
        c.execute("INSERT INTO users (username, password_hash) VALUES (?,?)",
                  (username, password_hash))
        c.execute("INSERT OR IGNORE INTO player_stats (username) VALUES (?)", (username,))
        c.commit()
        c.close()
        return True
    except sqlite3.IntegrityError:
        return False


def get_user(username: str):
    c = _conn()
    row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    c.close()
    return dict(row) if row else None


# ── Player stats ───────────────────────────────────────────────────────────────

def get_stats(username: str) -> dict:
    c = _conn()
    row = c.execute("SELECT * FROM player_stats WHERE username=?", (username,)).fetchone()
    c.close()
    return dict(row) if row else {"username": username, "skill": 1000.0, "solves": 0}


def upsert_stats(username: str, skill: float, solves: int):
    c = _conn()
    c.execute("""
        INSERT INTO player_stats (username, skill, solves) VALUES (?,?,?)
        ON CONFLICT(username) DO UPDATE SET skill=excluded.skill, solves=excluded.solves
    """, (username, skill, solves))
    c.commit()
    c.close()


def all_stats() -> list:
    c = _conn()
    rows = c.execute(
        "SELECT username, skill, solves FROM player_stats ORDER BY skill DESC"
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


# ── Problem stats ──────────────────────────────────────────────────────────────

def upsert_problem_stats(problem_id: str, difficulty: float, attempts: int):
    c = _conn()
    c.execute("""
        INSERT INTO problem_stats (problem_id, difficulty, attempts) VALUES (?,?,?)
        ON CONFLICT(problem_id) DO UPDATE SET
            difficulty=excluded.difficulty, attempts=excluded.attempts
    """, (problem_id, difficulty, attempts))
    c.commit()
    c.close()


def all_problem_stats() -> list:
    c = _conn()
    rows = c.execute(
        "SELECT problem_id, difficulty, attempts FROM problem_stats"
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]
