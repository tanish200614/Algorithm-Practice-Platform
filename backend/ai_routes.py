from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class InterviewTurnRequest(BaseModel):
    problem_title: str
    problem_description: str
    code: str
    complexity: str = "Unknown"
    approach: str = "Unknown"
    history: list[dict] = []
    message: str


@router.post("/ai/interview")
async def interview_endpoint(req: InterviewTurnRequest):
    try:
        from ai_features import interview_turn
        result = await interview_turn(
            req.problem_title,
            req.problem_description,
            req.code,
            req.complexity,
            req.approach,
            req.history,
            req.message,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"Unexpected error: {e}")
