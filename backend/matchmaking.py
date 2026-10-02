import asyncio, random, string
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from problems import PROBLEMS
from rooms import rooms, make_room_code
from ml import elo
from auth import token_from_query

router = APIRouter()

_queue: list[dict] = []
_lock = asyncio.Lock()


def _pick_problem() -> str:
    return random.choice(list(PROBLEMS.keys()))


def _create_match_room(problem_id: str) -> str:
    code = make_room_code()
    rooms[code] = {
        "problem_id": problem_id,
        "players": {},
        "status": "waiting",
        "connections": {},
        "tournament_callback": None,
    }
    return code


@router.websocket("/ws/queue")
async def queue_ws(websocket: WebSocket, token: str = Query(default=None)):
    name = token_from_query(token) or "Guest"
    elo_score = elo.get_skill(name)

    await websocket.accept()
    await websocket.send_json({
        "type": "searching",
        "name": name,
        "elo": round(elo_score),
        "queue_size": len(_queue),
    })

    entry = {"name": name, "elo": elo_score, "ws": websocket}
    matched_info = None

    async with _lock:
        # Find closest ELO match already waiting
        best_idx, best_diff = None, float("inf")
        for i, e in enumerate(_queue):
            diff = abs(e["elo"] - elo_score)
            if diff < best_diff:
                best_diff, best_idx = diff, i

        if best_idx is not None:
            opponent = _queue.pop(best_idx)
            problem_id = _pick_problem()
            room_code = _create_match_room(problem_id)
            matched_info = {
                "room_code": room_code,
                "problem_id": problem_id,
                "problem_title": PROBLEMS[problem_id]["title"],
                "opponent_ws": opponent["ws"],
                "opponent_name": opponent["name"],
                "self_name": name,
            }
        else:
            _queue.append(entry)

    if matched_info:
        msg_self = {
            "type": "matched",
            "room_code": matched_info["room_code"],
            "problem_id": matched_info["problem_id"],
            "problem_title": matched_info["problem_title"],
            "opponent": matched_info["opponent_name"],
        }
        await websocket.send_json(msg_self)
        try:
            await matched_info["opponent_ws"].send_json(
                {**msg_self, "opponent": matched_info["self_name"]}
            )
        except Exception:
            pass
        return

    # No match yet, wait in queue
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
                if data.get("type") == "cancel":
                    break
            except asyncio.TimeoutError:
                # Heartbeat so client knows we're alive
                try:
                    await websocket.send_json({
                        "type": "still_searching",
                        "queue_size": len(_queue),
                    })
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        async with _lock:
            try:
                _queue.remove(entry)
            except ValueError:
                pass  # already removed when matched
