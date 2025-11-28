import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from problems import PROBLEMS, LANGUAGES, language_available
from runner import run_submission
from sandbox import sandbox_status
from benchmarks import compile_to_assembly, run_cpp_benchmark_with_opt
from ml import elo, solve_times, difficulty
from auth import hash_password, verify_password, create_token, get_current_user
from database import create_user, get_user, get_stats, all_stats

router = APIRouter()


# ── Auth ───────────────────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(req: AuthRequest):
    if not re.match(r'^[a-zA-Z0-9_]{3,16}$', req.username):
        raise HTTPException(400, "Username must be 3-16 alphanumeric characters")
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if not create_user(req.username, hash_password(req.password)):
        raise HTTPException(409, "Username already taken")
    token = create_token(req.username)
    return {"token": token, "username": req.username}


@router.post("/login")
def login(req: AuthRequest):
    user = get_user(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid username or password")
    token = create_token(req.username)
    return {"token": token, "username": req.username}


@router.get("/me")
def me(username: str = Depends(get_current_user)):
    stats = get_stats(username)
    skill = stats["skill"]
    tier = elo.tier(username)
    rec = elo.recommend(username, list(PROBLEMS.keys()))
    return {
        "username": username,
        "skill": round(skill),
        "tier": tier,
        "solves": stats["solves"],
        "recommendation": {"id": rec, "title": PROBLEMS[rec]["title"]},
    }


# ── Code execution ────────────────────────────────────────────────────────────

class CodeRequest(BaseModel):
    code: str
    language: str = "python"


@router.post("/run")
def run_code(req: CodeRequest):
    lang = req.language.lower()
    if lang not in LANGUAGES:
        raise HTTPException(400, f"Unsupported language: {req.language}")
    try:
        return run_submission(req.code, lang)
    except Exception as e:
        return {"stdout": "", "stderr": f"Execution failed: {e}", "time_ms": 0}


@router.get("/sandbox")
def get_sandbox_status():
    """How submissions are being isolated right now."""
    return sandbox_status()


# ── Metadata ──────────────────────────────────────────────────────────────────

@router.get("/languages")
def get_languages():
    return [
        {"id": k, "label": v["label"], "available": language_available(k)}
        for k, v in LANGUAGES.items()
    ]


@router.get("/problems")
def list_problems():
    return [
        {
            "id": p["id"],
            "title": p["title"],
            "description": p["description"],
            **difficulty.score(p["description"], p["id"], elo),
        }
        for p in PROBLEMS.values()
    ]


@router.get("/player/{name}")
def get_player(name: str):
    skill = round(elo.get_skill(name))
    tier = elo.tier(name)
    solves = elo._solve_counts.get(name, 0)
    rec = elo.recommend(name, list(PROBLEMS.keys()))
    rec_title = PROBLEMS[rec]["title"]
    st = solve_times.stats(list(PROBLEMS.keys())[0]) if PROBLEMS else None
    return {
        "name": name,
        "skill": skill,
        "tier": tier,
        "solves": solves,
        "recommendation": {"id": rec, "title": rec_title},
    }


@router.get("/leaderboard")
def get_leaderboard():
    rows = all_stats()
    return [
        {"name": r["username"], "skill": round(r["skill"]),
         "tier": elo.tier(r["username"]), "solves": r["solves"]}
        for r in rows
    ]


# ── Assembly viewer ───────────────────────────────────────────────────────────

class AsmRequest(BaseModel):
    code: str
    problem_id: str = "two_sum"


@router.post("/asm")
def get_assembly(req: AsmRequest):
    if not language_available("cpp"):
        return {"error": "No C++ toolchain available on this server"}

    asm_text, err = compile_to_assembly(req.code)
    if err:
        return {"error": err[:500]}

    # Benchmark the same solution at both optimisation levels so the
    # assembly is paired with what it actually costs to run.
    o0 = run_cpp_benchmark_with_opt(req.code, req.problem_id, 3000, "-O0")
    o2 = run_cpp_benchmark_with_opt(req.code, req.problem_id, 3000, "-O2")

    speedup = None
    if o0 and o2 and o2.get("ms") and o2["ms"] > 0.05 and o0.get("ms"):
        speedup = round(o0["ms"] / o2["ms"], 1)
        if speedup < 1.2:
            speedup = None

    return {
        "asm": asm_text,
        "o0_ms": round(o0["ms"], 3) if o0 and o0.get("ms") else None,
        "o2_ms": round(o2["ms"], 3) if o2 and o2.get("ms") else None,
        "speedup": speedup,
    }


# ── Health check ──────────────────────────────────────────────────────────────

@router.get("/")
def home():
    return {"message": "Algorithm Practice Backend is running"}
