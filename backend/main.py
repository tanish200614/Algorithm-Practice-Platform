import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import router as code_router
from rooms import router as rooms_router
from matchmaking import router as queue_router
from tournament import router as tournament_router
from auth import using_dev_secret
from database import init_db, all_stats
from ml import elo
from sandbox import sandbox_status

# Everything the API serves lives under one prefix so a reverse proxy has a
# single route to forward, instead of a list of top-level paths that has to be
# kept in sync with the router every time an endpoint is added.
API_PREFIX = "/api"

# In production the frontend is served from the same origin, so no cross-origin
# grant is needed at all. ALLOWED_ORIGINS exists for split deployments; the
# default is the local Vite dev server rather than "*".
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

    if using_dev_secret():
        print(
            "[auth] WARNING: signing tokens with the built-in development key. "
            "Set SECRET_KEY — anyone who knows the default can mint valid tokens."
        )

    status = sandbox_status()
    if status["isolated"]:
        print(f"[sandbox] isolating submissions via {status['detail']}")
    else:
        # Name the languages rather than saying nothing is isolated: in
        # "partial" mode some of them are, and a blanket warning is both
        # alarming and inaccurate.
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
app.include_router(rooms_router, prefix=API_PREFIX)
app.include_router(queue_router, prefix=API_PREFIX)
app.include_router(tournament_router, prefix=API_PREFIX)


@app.get("/health")
def health():
    """Unprefixed so a load balancer health check needs no path rewriting."""
    return {"status": "ok", "sandbox": sandbox_status()["mode"]}
