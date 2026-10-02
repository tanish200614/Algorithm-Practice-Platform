import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import router as code_router
from ai_routes import router as ai_router
from rooms import router as rooms_router
from matchmaking import router as queue_router
from tournament import router as tournament_router
from auth import using_dev_secret
from database import all_problem_stats, all_stats, init_db
from ml import elo
from sandbox import sandbox_status

# Everything is under one prefix so a reverse proxy only needs one rule.
API_PREFIX = "/api"

# In production the frontend is on the same origin, so CORS isn't needed.
# ALLOWED_ORIGINS is for split deployments and defaults to the Vite dev server.
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    # Seed the in-memory ELO tracker from the database so ratings and solve
    # counts survive a restart.
    for row in all_stats():
        elo._skills[row["username"]] = row["skill"]
        elo._solve_counts[row["username"]] = row["solves"]

    # Load difficulties too, otherwise ratings won't match the problems they
    # were earned against.
    for row in all_problem_stats():
        elo._difficulties[row["problem_id"]] = row["difficulty"]
        elo._attempts[row["problem_id"]] = row["attempts"]

    if using_dev_secret():
        print(
            "[auth] WARNING: signing tokens with the built-in development key. "
            "Set SECRET_KEY — anyone who knows the default can mint valid tokens."
        )

    status = sandbox_status()
    if status["isolated"]:
        print(f"[sandbox] isolating submissions via {status['detail']}")
    else:
        # List the languages instead of saying nothing is isolated, since in
        # "partial" mode some of them are.
        loose = [lang for lang, ok in status["languages"].items() if not ok]
        safe = [lang for lang, ok in status["languages"].items() if ok]
        print(
            f"[sandbox] WARNING: mode '{status['mode']}' — "
            f"{', '.join(loose)} run on the host WITHOUT isolation"
            + (f" ({', '.join(safe)} isolated)" if safe else "")
            + f". {status['detail']}"
        )

    yield


app = FastAPI(title="AlgoBattle", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(code_router, prefix=API_PREFIX)
app.include_router(ai_router, prefix=API_PREFIX)
app.include_router(rooms_router, prefix=API_PREFIX)
app.include_router(queue_router, prefix=API_PREFIX)
app.include_router(tournament_router, prefix=API_PREFIX)


@app.get("/health")
def health():
    """No /api prefix so load balancer health checks work without rewriting."""
    return {"status": "ok", "sandbox": sandbox_status()["mode"]}
