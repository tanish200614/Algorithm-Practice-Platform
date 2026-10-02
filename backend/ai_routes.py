"""AI endpoints. These return 503 if no API key is set."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from generator import generate_problem
from interviewer import interview_turn
from llm import LLMUnavailable, cache_stats

router = APIRouter(prefix="/ai", tags=["ai"])


class GenerateRequest(BaseModel):
    topic: str
    difficulty: str = "medium"


class InterviewRequest(BaseModel):
    message: str
    history: list = []


@router.post("/generate-problem")
def generate(req: GenerateRequest, username: str = Depends(get_current_user)):
    try:
        return generate_problem(req.topic, req.difficulty)
    except LLMUnavailable as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        # Every attempt failed validation. That's a real result, not a server error.
        raise HTTPException(422, str(e))


@router.post("/interview")
def interview(req: InterviewRequest, username: str = Depends(get_current_user)):
    try:
        return interview_turn(req.history, req.message)
    except LLMUnavailable as e:
        raise HTTPException(503, str(e))


@router.get("/cache")
def cache(username: str = Depends(get_current_user)):
    return cache_stats()
