from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import router as code_router
from rooms import router as rooms_router
from matchmaking import router as queue_router
from tournament import router as tournament_router
from database import init_db, all_stats
from ml import elo

app = FastAPI()


@app.on_event("startup")
def startup():
    init_db()
    # Seed in-memory ELO from persisted DB so ratings survive restarts
    for row in all_stats():
        elo._skills[row["username"]] = row["skill"]
        elo._solve_counts[row["username"]] = row["solves"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(code_router)
app.include_router(rooms_router)
app.include_router(queue_router)
app.include_router(tournament_router)
