import asyncio, random, string
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel

from problems import PROBLEMS
from rooms import rooms, make_room_code
from ml import elo
from auth import token_from_query

router = APIRouter()
tournaments: dict[str, "TournamentRoom"] = {}

MIN_PLAYERS = 4
MAX_PLAYERS = 8


def make_tournament_code() -> str:
    return "T" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


class TournamentRoom:
    def __init__(self, code: str, host: str):
        self.code = code
        self.host = host
        self.players: dict[str, dict] = {}  # name → {ws, alive, elo}
        self.bracket: list[dict] = []       # list of completed/active rounds
        self.status = "lobby"               # lobby | active | done
        self.problem_pool = list(PROBLEMS.keys())
        random.shuffle(self.problem_pool)
        self.problem_idx = 0

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _next_problem(self) -> str:
        pid = self.problem_pool[self.problem_idx % len(self.problem_pool)]
        self.problem_idx += 1
        return pid

    def _seed_bracket(self, alive: list[str]) -> list[dict]:
        seeded = sorted(alive, key=lambda n: elo.get_skill(n), reverse=True)
        size = 1
        while size < len(seeded):
            size *= 2
        padded = seeded + [None] * (size - len(seeded))
        # Standard seeding: 1 vs last, 2 vs second-last, etc.
        matches = []
        for i in range(size // 2):
            matches.append({
                "p1": padded[i],
                "p2": padded[size - 1 - i],
                "winner": None,
                "room_code": None,
            })
        return matches

    def _player_list(self) -> list[dict]:
        return [
            {"name": n, "elo": p["elo"], "alive": p["alive"]}
            for n, p in self.players.items()
        ]

    def _bracket_view(self) -> list[dict]:
        return [
            {
                "round": i + 1,
                "problem_id": r["problem_id"],
                "problem_title": PROBLEMS[r["problem_id"]]["title"],
                "matches": [
                    {"p1": m["p1"], "p2": m["p2"], "winner": m["winner"]}
                    for m in r["matches"]
                ],
            }
            for i, r in enumerate(self.bracket)
        ]

    async def _broadcast(self, msg: dict, exclude: str = None):
        for name, player in list(self.players.items()):
            if name == exclude:
                continue
            try:
                await player["ws"].send_json(msg)
            except Exception:
                pass

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def add_player(self, name: str, ws: WebSocket):
        self.players[name] = {
            "ws": ws,
            "alive": True,
            "elo": round(elo.get_skill(name)),
        }
        await self._broadcast(
            {
                "type": "player_joined",
                "name": name,
                "players": self._player_list(),
                "count": len(self.players),
            },
            exclude=name,
        )
        await ws.send_json({
            "type": "lobby_state",
            "code": self.code,
            "host": self.host,
            "players": self._player_list(),
            "status": self.status,
            "min_players": MIN_PLAYERS,
            "max_players": MAX_PLAYERS,
        })

    def remove_player(self, name: str):
        self.players.pop(name, None)

    async def start(self) -> bool:
        if len(self.players) < MIN_PLAYERS:
            return False
        self.status = "active"
        await self._broadcast({
            "type": "tournament_started",
            "total_players": len(self.players),
        })
        await self._start_round()
        return True

    async def _start_round(self):
        alive = [n for n, p in self.players.items() if p["alive"]]

        if len(alive) <= 1:
            winner = alive[0] if alive else "Nobody"
            self.status = "done"
            await self._broadcast({
                "type": "tournament_done",
                "winner": winner,
                "bracket": self._bracket_view(),
            })
            return

        problem_id = self._next_problem()
        matches = self._seed_bracket(alive)
        self.bracket.append({"problem_id": problem_id, "matches": matches})

        # Auto-resolve byes (p2 is None → p1 advances)
        for m in matches:
            if m["p2"] is None:
                m["winner"] = m["p1"]

        round_num = len(self.bracket)
        await self._broadcast({
            "type": "round_start",
            "round": round_num,
            "total_players": len(alive),
            "problem_id": problem_id,
            "problem_title": PROBLEMS[problem_id]["title"],
            "bracket": self._bracket_view(),
        })

        # Create rooms for real (non-bye) matches
        for m in matches:
            if not m["p1"] or not m["p2"]:
                continue

            room_code = make_room_code()
            m["room_code"] = room_code

            p1_name, p2_name = m["p1"], m["p2"]

            async def _on_done(winner, _m=m, _p1=p1_name, _p2=p2_name):
                # On tie, higher ELO advances
                if winner == "tie":
                    winner = _p1 if elo.get_skill(_p1) >= elo.get_skill(_p2) else _p2
                _m["winner"] = winner
                await self._check_round_done()

            rooms[room_code] = {
                "problem_id": problem_id,
                "players": {},
                "status": "waiting",
                "connections": {},
                "tournament_callback": _on_done,
            }

            for p_name, opp_name in [(p1_name, p2_name), (p2_name, p1_name)]:
                try:
                    await self.players[p_name]["ws"].send_json({
                        "type": "match_ready",
                        "room_code": room_code,
                        "problem_id": problem_id,
                        "problem_title": PROBLEMS[problem_id]["title"],
                        "opponent": opp_name,
                        "round": round_num,
                    })
                except Exception:
                    pass

    async def _check_round_done(self):
        current = self.bracket[-1]
        if not all(m["winner"] is not None for m in current["matches"]):
            return

        round_num = len(self.bracket)
        winners = [m["winner"] for m in current["matches"]]

        for name in self.players:
            self.players[name]["alive"] = name in winners

        await self._broadcast({
            "type": "round_done",
            "round": round_num,
            "advancing": winners,
            "bracket": self._bracket_view(),
        })

        await asyncio.sleep(5)
        await self._start_round()


# ── HTTP endpoints ─────────────────────────────────────────────────────────────

class CreateTournamentBody(BaseModel):
    username: str = "Host"


@router.post("/tournament/create")
async def create_tournament(body: CreateTournamentBody):
    code = make_tournament_code()
    tournaments[code] = TournamentRoom(code, body.username)
    return {"tournament_code": code}


@router.get("/tournament/{code}")
async def get_tournament(code: str):
    t = tournaments.get(code.upper())
    if not t:
        return {"error": "Tournament not found"}
    return {
        "code": t.code,
        "host": t.host,
        "status": t.status,
        "players": t._player_list(),
        "bracket": t._bracket_view(),
    }


# ── WebSocket ──────────────────────────────────────────────────────────────────

@router.websocket("/ws/tournament/{code}")
async def tournament_ws(
    websocket: WebSocket,
    code: str,
    token: str = Query(default=None),
):
    code = code.upper()
    name = token_from_query(token) or "Guest"

    await websocket.accept()

    t = tournaments.get(code)
    if not t:
        await websocket.send_json({"type": "error", "msg": "Tournament not found"})
        await websocket.close()
        return

    if t.status != "lobby":
        await websocket.send_json({"type": "error", "msg": "Tournament already started"})
        await websocket.close()
        return

    if len(t.players) >= MAX_PLAYERS:
        await websocket.send_json({"type": "error", "msg": "Tournament is full (max 8 players)"})
        await websocket.close()
        return

    await t.add_player(name, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "start":
                if name != t.host:
                    await websocket.send_json({"type": "error", "msg": "Only the host can start"})
                elif len(t.players) < MIN_PLAYERS:
                    await websocket.send_json({
                        "type": "error",
                        "msg": f"Need at least {MIN_PLAYERS} players (have {len(t.players)})",
                    })
                else:
                    await t.start()

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        t.remove_player(name)
        if t.players:
            await t._broadcast({
                "type": "player_left",
                "name": name,
                "players": t._player_list(),
                "count": len(t.players),
            })
        elif t.status == "lobby":
            tournaments.pop(code, None)
