"""
WebSocket load test: N concurrent 1v1 rooms, measuring message latency.

Each match is two real players (distinct accounts) connected to the same battle
room over WebSockets. Every player pings at a fixed interval for the duration
of the test and records the round-trip time to the server's pong, which goes
through the same receive loop and JSON path as every other battle message.

    pip install websockets httpx
    python loadtest/ws_load.py --base https://api.example.com --matches 50 --duration 60

Accounts: by default it registers throwaway users (lt<run><n>). If you pass
--secret (the server's SECRET_KEY), it mints tokens locally instead and
creates no accounts.

Reports median / p95 / p99 round-trip time and any connection errors.
"""

import argparse
import asyncio
import json
import secrets
import statistics
import time

import httpx
import websockets


def pct(values, p):
    if not values:
        return float("nan")
    s = sorted(values)
    k = min(len(s) - 1, max(0, round(p / 100 * (len(s) - 1))))
    return s[k]


async def get_tokens(client, api, n, secret):
    run = secrets.token_hex(3)
    names = [f"lt{run}{i}" for i in range(n)]
    if secret:
        import jwt  # pyjwt

        exp = int(time.time()) + 3600
        return [jwt.encode({"sub": u, "exp": exp}, secret, algorithm="HS256") for u in names]

    sem = asyncio.Semaphore(10)  # bcrypt is slow; don't stampede /register

    async def reg(u):
        async with sem:
            r = await client.post(f"{api}/register", json={"username": u, "password": secrets.token_hex(8)})
            r.raise_for_status()
            return r.json()["token"]

    return await asyncio.gather(*(reg(u) for u in names))


async def player(ws_base, room, token, duration, interval, rtts, errors, started):
    url = f"{ws_base}/ws/{room}?token={token}"
    try:
        async with websockets.connect(url, open_timeout=20, max_queue=None) as ws:
            pending = {}

            async def reader():
                async for raw in ws:
                    msg = json.loads(raw)
                    t = msg.get("type")
                    if t == "pong":
                        sent = pending.pop("ping", None)
                        if sent is not None:
                            rtts.append((time.perf_counter() - sent) * 1000)
                    elif t == "error":
                        errors.append(msg.get("msg"))

            task = asyncio.create_task(reader())
            await started.wait()
            stop_at = time.perf_counter() + duration
            while time.perf_counter() < stop_at:
                # One ping in flight per player, so RTTs aren't queued behind
                # each other and a slow server shows up as slow, not as backlog.
                if "ping" not in pending:
                    pending["ping"] = time.perf_counter()
                    await ws.send(json.dumps({"type": "ping"}))
                await asyncio.sleep(interval)
            task.cancel()
    except Exception as e:  # noqa: BLE001
        errors.append(f"{type(e).__name__}: {e}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000",
                    help="Origin serving /api (e.g. https://api.example.com)")
    ap.add_argument("--matches", type=int, default=50)
    ap.add_argument("--duration", type=float, default=30.0, help="seconds of pinging")
    ap.add_argument("--interval", type=float, default=0.5, help="seconds between pings per player")
    ap.add_argument("--secret", default=None, help="server SECRET_KEY: mint tokens, skip registration")
    args = ap.parse_args()

    api = args.base.rstrip("/") + "/api"
    ws_base = api.replace("https://", "wss://").replace("http://", "ws://")

    async with httpx.AsyncClient(timeout=30) as client:
        print(f"Preparing {args.matches} matches ({args.matches * 2} players)…")
        tokens = await get_tokens(client, api, args.matches * 2, args.secret)
        rooms = []
        for _ in range(args.matches):
            r = await client.post(f"{api}/room/create", json={"problem_id": "two_sum"})
            r.raise_for_status()
            rooms.append(r.json()["room_code"])

    rtts, errors = [], []
    started = asyncio.Event()
    tasks = []
    for i, room in enumerate(rooms):
        for p in range(2):
            tasks.append(asyncio.create_task(player(
                ws_base, room, tokens[2 * i + p], args.duration, args.interval,
                rtts, errors, started)))

    await asyncio.sleep(10)  # let every socket connect before measuring
    started.set()
    print(f"Connected. Pinging for {args.duration:.0f}s…")
    await asyncio.gather(*tasks)

    print()
    print(f"matches            {args.matches} concurrent ({args.matches * 2} sockets)")
    print(f"messages measured  {len(rtts)}")
    if rtts:
        print(f"RTT median         {statistics.median(rtts):.1f} ms")
        print(f"RTT p95            {pct(rtts, 95):.1f} ms")
        print(f"RTT p99            {pct(rtts, 99):.1f} ms")
    print(f"errors             {len(errors)}")
    for e in sorted(set(errors))[:5]:
        print(f"  - {e}")


if __name__ == "__main__":
    asyncio.run(main())
