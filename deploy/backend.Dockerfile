# API server.
#
# This image ships the Docker *client* but no daemon: the backend launches
# sandbox containers as siblings on the host's daemon through a mounted
# socket. See deploy/README.md — that socket is host-root-equivalent, which is
# why the API runs on its own instance rather than sharing one.

# Take the CLI from the official image rather than Debian's docker.io package:
# that package is built around the daemon, and on slim it does not leave a
# usable /usr/bin/docker behind. This is a pinned, single static binary.
FROM docker:27-cli AS dockercli

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /app

# Dependencies first so edits to application code don't invalidate this layer.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Refuse to fall back to unisolated host execution in a deployed environment.
ENV SANDBOX_MODE=docker \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# 127.0.0.1, not localhost: localhost can resolve to ::1 while uvicorn is bound
# to IPv4, and the check then fails against a perfectly healthy server.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
