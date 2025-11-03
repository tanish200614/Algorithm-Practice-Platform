# Sandbox image for untrusted Python submissions.
#
# Nothing in here talks to the network or the host — the container is
# started with --network none, all capabilities dropped, and a read-only
# view of everything except /work.
FROM python:3.12-slim

# Unprivileged user. Submissions never run as root.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin sandbox

# /work is where the harness is copied in and where the process may write.
# World-writable because `docker cp` lands files as root while the process
# runs as uid 1000.
RUN mkdir -p /work && chmod 1777 /work

WORKDIR /work
USER 1000:1000

# Don't write .pyc files or buffer stdout — we read stdout after exit.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

ENTRYPOINT ["python3"]
