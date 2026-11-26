"""
AI endpoints. These return 503 if no API key is set.

Both cost money per call, so on a public deployment they are limited per user
(fixed windows, counted in Redis when it is configured). Problem generation is
additionally restricted to the ADMIN role, which only the GitHub login service
(auth-service/) can grant.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import kv
from auth import get_current_user, require_role
from generator import generate_problem
from interviewer import interview_turn
from llm import LLMUnavailable, cache_stats

router = APIRouter(prefix="/ai", tags=["ai"])

INTERVIEW_LIMIT_PER_HOUR = int(os.environ.get("AI_INTERVIEW_LIMIT_PER_HOUR", "40"))
GENERATE_LIMIT_PER_HOUR = int(os.environ.get("AI_GENERATE_LIMIT_PER_HOUR", "10"))


def _rate_limit(kind: str, username: str, limit: int):
    if limit <= 0:
        return
    if kv.store().hit_window(f"{kind}:{username}", 3600) > limit:
        raise HTTPException(429, f"Limit is {limit} {kind} requests per hour — try again later")


class GenerateRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=80)
    difficulty: str = "medium"


class InterviewRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    history: list = Field(default_factory=list, max_length=60)


@router.post("/generate-problem")
def generate(req: GenerateRequest, username: str = Depends(require_role("ADMIN"))):
    if req.difficulty.strip().lower() not in {"easy", "medium", "hard"}:
        raise HTTPException(400, "difficulty must be easy, medium, or hard")
    _rate_limit("generate", username, GENERATE_LIMIT_PER_HOUR)
    try:
        return generate_problem(req.topic, req.difficulty)
    except LLMUnavailable as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        # Every attempt failed validation. That's a real result, not a server error.
        raise HTTPException(422, str(e))


@router.post("/interview")
def interview(req: InterviewRequest, username: str = Depends(get_current_user)):
    _rate_limit("interview", username, INTERVIEW_LIMIT_PER_HOUR)
    try:
        return interview_turn(req.history, req.message)
    except LLMUnavailable as e:
        raise HTTPException(503, str(e))


@router.get("/cache")
def cache(username: str = Depends(get_current_user)):
    return cache_stats()
