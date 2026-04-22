# Deploying AlgoBattle

## Shape of the system

```
                    Application Load Balancer
                    /api/*, /health  |  everything else
                            |                 |
                     ┌──────┴─────┐    ┌──────┴──────┐
                     │  backend   │    │  frontend   │
                     │  uvicorn   │    │  nginx+SPA  │
                     └──────┬─────┘    └─────────────┘
                            │ /var/run/docker.sock
                     ┌──────┴──────────────────────┐
                     │  sandbox containers          │
                     │  python / cpp / java         │
                     │  --network none, uid 10001   │
                     └──────────────────────────────┘
```

The load balancer routes by path: `/api/*` and `/health` go to the API, and
everything else is the single-page app. The API never executes a submission
itself — it asks the host's Docker daemon to start a throwaway container per
run.

## Two constraints worth understanding before changing anything

**The API cannot run on Fargate.** Isolating submissions means starting sibling
containers on the host daemon, which needs `/var/run/docker.sock` mounted.
Fargate does not expose one. That is why the stack uses the EC2 launch type.

The tradeoff is real and worth stating plainly: access to that socket is
equivalent to root on the instance. A container escape in the API would own the
host. The mitigations here are that the container instances run nothing else,
they have no inbound access except from the load balancer, and IMDSv2 is
required so a request-forgery bug cannot read instance credentials. A stronger
design would move execution to a separate pool of workers reached over a queue,
so the API never touches a daemon socket at all.

**The API is pinned to one task.** Battle rooms, the matchmaking queue, and
tournament brackets live in Python dictionaries in the process. Two players
routed to different tasks would sit in rooms that cannot see each other. The
service is therefore `DesiredCount: 1`, and the target group uses stickiness so
a reconnecting player returns to the task holding their room.

Raising that count requires moving the shared state out of process first —
ElastiCache for Redis, with rooms as hashes and the broadcast fan-out over
pub/sub. Until then, scaling up means a bigger instance, not more tasks.

## Deploying

```bash
aws cloudformation deploy \
  --template-file deploy/aws/cloudformation.yml \
  --stack-name algobattle \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      VpcId=vpc-xxxxxxxx \
      PublicSubnetIds=subnet-aaaa,subnet-bbbb \
      CertificateArn=arn:aws:acm:us-east-1:...:certificate/...
```

The stack creates the ECR repositories but no images, so the first deploy
leaves the services unable to start. Push images once with the `Deploy`
workflow (tag a release, or run it manually), and the services converge.

`CertificateArn` is optional. Without it the listener serves plain HTTP, which
is fine for a demo but means passwords cross the network in the clear — set it
for anything real.

### What CI does

- **CI** runs on every pull request: backend tests (with the Python sandbox
  image built, so the isolation tests assert against real containers), the
  frontend build, and both application images built but not pushed.
- **Deploy** runs on a `v*` tag or manually. It authenticates with OIDC rather
  than stored AWS keys, pushes images tagged with both the commit SHA and
  `latest`, forces a new deployment, then waits for `services-stable` and polls
  `/health`. The deployment circuit breaker rolls back automatically if the new
  tasks fail to become healthy.

Rolling back is `aws ecs update-service` against the task definition revision
that pinned the previous SHA.

## Running it locally

```bash
./sandbox/build.sh                      # required — see below
export SECRET_KEY=$(openssl rand -hex 32)
docker compose up --build
open http://localhost:8080
```

The sandbox images have to exist first. The API image sets
`SANDBOX_MODE=docker`, which makes the backend fail a submission rather than
fall back to running it unisolated on the host — the right way round for
untrusted code, but it does mean a missing image looks like a broken run. The
lobby surfaces the sandbox mode, and the backend logs it at startup.

For frontend work without containers:

```bash
cd backend && uvicorn main:app --reload          # :8000
cd frontend && npm run dev                       # :5173
```

There the backend falls back to executing submissions on your machine under
rlimits, because `SANDBOX_MODE` defaults to `auto`. That fallback constrains
CPU and wall-clock but does **not** isolate the filesystem or the network, and
on macOS it cannot cap memory at all. It is for convenience while developing,
not for running code you did not write.

## Operational notes

- **Instance sizing** is driven by concurrent submissions, not by the API. Each
  sandbox container may take up to 768 MB (Java), so `t3.medium` supports only
  a handful of simultaneous benchmarks.
- **The C++ sandbox image is ~2 GB** because it carries a full toolchain.
  Instances pre-pull the sandbox images at boot; without that, the first
  submission after a scale-out pays the pull inside a request and the player
  sees a timeout.
- **SQLite lives on the instance** at `/opt/algobattle/data`, which means
  ratings do not survive replacing the instance. Moving to RDS is the fix, and
  it pairs naturally with the Redis work above.
- **Idle timeouts** are raised to 300s on the load balancer and in nginx. A
  benchmark compiles and runs a submission at six input sizes, which outlasts
  the 60s defaults.
