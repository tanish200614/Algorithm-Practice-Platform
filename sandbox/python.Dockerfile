# Sandbox image for untrusted Python submissions.
#
# Nothing in here talks to the network or the host — the container is
# started with --network none, all capabilities dropped, and a read-only
# view of everything except /work.
FROM python:3.12-slim

# Unprivileged user. Submissions never run as root.
# A high uid so it cannot collide with a user the base image already
# ships — the eclipse-temurin base owns 1000 as "ubuntu", and useradd
# fails the build on that collision.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin sandbox

# /work is where the harness is copied in and where the process may write.
# World-writable because `docker cp` lands files as root while the process
# runs as the sandbox uid.
RUN mkdir -p /work && chmod 1777 /work

WORKDIR /work
USER 10001:10001

# Don't write .pyc files or buffer stdout — we read stdout after exit.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

ENTRYPOINT ["python3"]
