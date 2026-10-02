import asyncio, random, string, time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from problems import PROBLEMS
from benchmarks import benchmark_solution


def _get_problem(problem_id: str) -> dict:
    return PROBLEMS[problem_id]
from ml import elo, solve_times, code_similarity
from auth import token_from_query
from database import get_stats, upsert_problem_stats, upsert_stats

router = APIRouter()
rooms: dict[str, dict] = {}


def make_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


async def broadcast(room: dict, message: dict):
    dead = []
    for pid, ws in room["connections"].items():
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(pid)
    for pid in dead:
        room["connections"].pop(pid, None)


@router.post("/room/create")
def create_room(body: dict):
    problem_id = body.get("problem_id", random.choice(list(PROBLEMS.keys())))
    code = make_room_code()
    rooms[code] = {
        "problem_id": problem_id,
        "players": {},
        "status": "waiting",
        "connections": {},
        "tournament_callback": None,
    }
    return {"room_code": code, "problem": _get_problem(problem_id)}


@router.get("/room/{room_code}")
def get_room(room_code: str):
    room = rooms.get(room_code.upper())
    if not room:
        return {"error": "Room not found"}
    return {
        "problem": _get_problem(room["problem_id"]),
        "status": room["status"],
        "player_count": len(room["players"]),
    }


@router.websocket("/ws/{room_code}")
async def battle_ws(websocket: WebSocket, room_code: str,
                    token: str = Query(default=None)):
    # Resolve player name: authenticated username takes priority over query param
    authed = token_from_query(token)
    player_name = authed or "Guest"
    room_code = room_code.upper()
    await websocket.accept()

    room = rooms.get(room_code)
    if not room:
        await websocket.send_json({"type": "error", "msg": "Room not found"})
        await websocket.close()
        return

    if len(room["players"]) >= 2 and player_name not in room["players"]:
        await websocket.send_json({"type": "error", "msg": "Room full"})
        await websocket.close()
        return

    player_id = player_name
    room["players"][player_id] = {"name": player_name, "code": "", "results": None, "ready": False,
                                   "join_time": time.monotonic()}
    room["connections"][player_id] = websocket

    await websocket.send_json({
        "type": "joined",
        "player_id": player_id,
        "problem": _get_problem(room["problem_id"]),
        "room_status": room["status"],
        "players": [p["name"] for p in room["players"].values()],
    })

    await broadcast(room, {
        "type": "player_joined",
        "players": [p["name"] for p in room["players"].values()],
        "count": len(room["players"]),
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "submit":
                if room["status"] != "waiting":
                    await websocket.send_json({"type": "error", "msg": "Race already started or done"})
                    continue

                room["players"][player_id]["code"] = data.get("code", "")
                room["players"][player_id]["language"] = data.get("language", "python")
                room["players"][player_id]["ready"] = True
                room["players"][player_id]["solve_ms"] = (
                    time.monotonic() - room["players"][player_id]["join_time"]
                ) * 1000

                await broadcast(room, {
                    "type": "player_ready",
                    "player": player_name,
                    "ready_count": sum(1 for p in room["players"].values() if p["ready"]),
                    "total": len(room["players"]),
                })

                if all(p["ready"] for p in room["players"].values()) and len(room["players"]) == 2:
                    room["status"] = "racing"
                    await broadcast(room, {"type": "race_start"})

                    player_ids = list(room["players"].keys())
                    codes = [room["players"][pid]["code"] for pid in player_ids]
                    problem_id = room["problem_id"]
                    loop = asyncio.get_event_loop()

                    async def run_and_stream(pid, code):
                        lang = room["players"][pid].get("language", "python")
                        result = await loop.run_in_executor(None, lambda: benchmark_solution(code, problem_id, lang))
                        room["players"][pid]["results"] = result
                        await broadcast(room, {
                            "type": "results",
                            "player": room["players"][pid]["name"],
                            "language": lang,
                            "data": result,
                        })

                    await asyncio.gather(
                        run_and_stream(player_ids[0], codes[0]),
                        run_and_stream(player_ids[1], codes[1]),
                    )

                    def score(pid):
                        r = room["players"][pid]["results"]
                        if not r or not r["results"]:
                            return 0
                        valid = [x for x in r["results"] if x["ms"] is not None and x["ok"] and x["ms"] > 0]
                        return sum(x["n"] / x["ms"] for x in valid)

                    s0, s1 = score(player_ids[0]), score(player_ids[1])
                    winner = (
                        room["players"][player_ids[0]]["name"] if s0 > s1 else
                        room["players"][player_ids[1]]["name"] if s1 > s0 else
                        "tie"
                    )

                    # ── ML signals ────────────────────────────────────────────
                    p0 = room["players"][player_ids[0]]
                    p1 = room["players"][player_ids[1]]
                    problem_id = room["problem_id"]

                    # Code similarity
                    similarity = code_similarity(p0["code"], p1["code"])

                    # Solve time percentiles (compute before adding so own time isn't included)
                    pct = {}
                    for pid in player_ids:
                        t = room["players"][pid].get("solve_ms")
                        name = room["players"][pid]["name"]
                        pct[name] = solve_times.percentile(problem_id, t) if t else None
                        if t:
                            solve_times.add(problem_id, t)

                    # ELO updates + persist to DB
                    elo_deltas = {}
                    for pid in player_ids:
                        name = room["players"][pid]["name"]
                        r = room["players"][pid]["results"]
                        solved = bool(r and r.get("results") and
                                      any(x.get("ok") for x in r["results"]))
                        elo_deltas[name] = elo.update(name, problem_id, solved)
                        upsert_stats(name, elo.get_skill(name), elo._solve_counts[name])

                    # elo.update() changes the problem rating too, so save both here.
                    upsert_problem_stats(
                        problem_id,
                        elo.get_difficulty(problem_id),
                        elo.get_attempts(problem_id),
                    )

                    # Recommendations
                    all_problems = list(PROBLEMS.keys())
                    recs = {room["players"][pid]["name"]: elo.recommend(room["players"][pid]["name"], all_problems)
                            for pid in player_ids}

                    room["status"] = "done"
                    if room.get("tournament_callback"):
                        asyncio.create_task(room["tournament_callback"](winner))
                    await broadcast(room, {
                        "type": "race_done",
                        "winner": winner,
                        "scores": {
                            p0["name"]: round(s0),
                            p1["name"]: round(s1),
                        },
                        "similarity": similarity,
                        "solve_time_ms": {room["players"][pid]["name"]: round(room["players"][pid].get("solve_ms", 0))
                                          for pid in player_ids},
                        "percentiles": pct,
                        "elo_deltas": elo_deltas,
                        "skills": {room["players"][pid]["name"]: round(elo.get_skill(room["players"][pid]["name"]))
                                   for pid in player_ids},
                        "recommendations": recs,
                    })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        room["connections"].pop(player_id, None)
        room["players"].pop(player_id, None)
        await broadcast(room, {
            "type": "player_left",
            "player": player_name,
            "players": [p["name"] for p in room["players"].values()],
        })
        if not room["players"]:
            rooms.pop(room_code, None)
