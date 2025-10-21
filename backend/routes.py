import subprocess, tempfile, os, re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from problems import PROBLEMS, LANGUAGES, detect_compiler
from runner import run_python, run_cpp, run_java
from benchmarks import run_cpp_benchmark_with_opt
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
    try:
        if lang == "cpp":
            stdout, stderr, duration, mem = run_cpp(req.code)
        elif lang == "java":
            stdout, stderr, duration, mem = run_java(req.code)
        else:
            stdout, stderr, duration, mem = run_python(req.code)
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "time_ms": 0, "memory_kb": 0}
    return {"stdout": stdout, "stderr": stderr, "time_ms": duration, "memory_kb": mem}


# ── Metadata ──────────────────────────────────────────────────────────────────

@router.get("/languages")
def get_languages():
    return [{"id": k, "label": v["label"], "available": v["available"]} for k, v in LANGUAGES.items()]


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
    if not detect_compiler("g++"):
        return {"error": "g++ not available on this server"}

    tmpdir = tempfile.mkdtemp()
    src = os.path.join(tmpdir, "solution.cpp")
    asm_path = os.path.join(tmpdir, "solution.s")

    if "int main(" not in req.code:
        full_code = f"""
#include <iostream>
#include <vector>
#include <algorithm>
#include <unordered_map>
#include <string>
using namespace std;

{req.code}

int main() {{ return 0; }}
"""
    else:
        full_code = req.code

    with open(src, "w") as f:
        f.write(full_code)

    asm_compiled = None
    for extra in [["-masm=intel"], []]:
        cp = subprocess.run(
            ["g++", "-S", "-O2", "-std=c++17", "-fverbose-asm"] + extra + [src, "-o", asm_path],
            capture_output=True, text=True, timeout=15
        )
        if cp.returncode == 0:
            asm_compiled = extra
            break

    if asm_compiled is None:
        return {"error": cp.stderr[:500]}

    with open(asm_path) as f:
        asm_text = f.read()

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
