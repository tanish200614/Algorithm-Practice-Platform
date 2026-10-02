# AlgoBattle

A real-time multiplayer platform where two people solve the same algorithm
problem and watch their solutions race. Both submissions are benchmarked across
growing input sizes, and the winner is whoever's code scales better, not
whoever typed first.

The interesting part is what happens after you submit: the platform measures
runtime at six input sizes, fits the timings in log-log space to recover the
complexity exponent, and tells you whether you wrote O(n) or O(n²). It will
also show you the generated x86 assembly for a C++ solution and what the
optimiser bought you.

## What's in it

**Racing.** Head-to-head rooms over WebSockets, ELO-based matchmaking that
pairs you with someone near your rating, and 4-8 player single-elimination
tournaments with ELO-seeded brackets.

**Measurement, not stopwatches.** A submission runs at n = 100 … 15000. Fitting
`log(ms)` against `log(n)` recovers the exponent directly, and because constant
factors cancel in log space, a slow O(n) solution still reads as linear and a
fast O(n²) one still reads as quadratic. The same fit is extrapolated after
three data points to skip an input size that would obviously time out, rather
than making everyone wait for it.

**Assembly viewer.** C++ solutions can be compiled to annotated assembly and
benchmarked at `-O0` and `-O2` side by side, so the optimiser's effect is a
concrete number rather than folklore.

**Approach clustering.** Submissions are tokenised, weighted by TF-IDF, and
grouped with cosine k-means, so the platform can tell you your hash-map
solution looks like 12 others and that your opponent solved it differently.

**Three languages.** Python, C++17, and Java, each with a hand-written
benchmark harness per problem so the timings are comparable.

## Running untrusted code

Every submission (test runs, benchmark harnesses, assembly dumps) goes
through [`backend/sandbox.py`](backend/sandbox.py), which puts it in a
throwaway per-language container:

| | |
|---|---|
| Network | `--network none`, no route to anything |
| User | uid 10001, `--cap-drop ALL`, `no-new-privileges` |
| Memory | 256-768 MB by language, swap disabled so the limit is real |
| CPU | capped share of one core |
| Processes | pid ceiling, which is what a fork bomb hits |
| Wall clock | hard timeout; the container is killed, not just detached from |

Compilation happens inside the sandbox too, so a compile-time bomb or a hostile
`#include` never reaches the host.

When the daemon or the images are missing, the backend degrades to running
submissions on the host under POSIX rlimits. That path constrains CPU and wall
clock but does **not** isolate the filesystem or the network, so it exists for
local development only: `GET /api/sandbox` reports the mode in force, the lobby
shows a banner when it is active, and setting `SANDBOX_MODE=docker` (which the
production image does) makes the backend fail the request instead.

## Layout

```
backend/     FastAPI: auth, rooms, matchmaking, tournaments,
             benchmarking, complexity detection, the sandbox
frontend/    React + Vite single-page app
sandbox/     One Dockerfile per language, plus build.sh
deploy/      Application images, compose stack, and the AWS stack
```

Worth reading first: `backend/sandbox.py` for the isolation model,
`backend/benchmarks.py` for the log-log fit, and `deploy/README.md` for why the
API runs on EC2 rather than Fargate.

## Getting it running

```bash
./sandbox/build.sh                      # build the per-language sandboxes
export SECRET_KEY=$(openssl rand -hex 32)
docker compose up --build
open http://localhost:8080
```

Without containers, for frontend work:

```bash
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
cd frontend && npm install && npm run dev
```

Tests:

```bash
cd backend && python -m pytest
```

The isolation tests assert against real containers and skip when the images
aren't built, so run `sandbox/build.sh` first if you want the full suite.

## Deploying

ECS behind an Application Load Balancer, described in
[`deploy/aws/cloudformation.yml`](deploy/aws/cloudformation.yml). CI runs tests
and builds images on every pull request; tagging a release pushes to ECR and
rolls the services, waiting for them to stabilise before reporting success.

See [`deploy/README.md`](deploy/README.md) for the deployment walkthrough and
the two architectural constraints: the Docker socket, and the in-process room
state that pins the API to a single task.

## Known limits

- **The API does not scale horizontally.** Rooms, the matchmaking queue, and
  brackets are in-process state. Moving them to Redis is the prerequisite.
- **SQLite lives on the instance**, so ratings don't survive replacing it. RDS
  is the fix.
- **Adding a problem is manual work.** Each one needs an input generator and a
  validator, plus a hand-written benchmark harness per language it should
  support. That is what keeps timings comparable across languages, but it means
  the catalog grows slowly.
