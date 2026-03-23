# Sandbox image for untrusted C++ submissions.
#
# Carries a compiler because submissions are compiled inside the sandbox
# too — a hostile #include or a compile-time bomb should not reach the host.
FROM gcc:13-bookworm

# A high uid so it cannot collide with a user the base image already
# ships — the eclipse-temurin base owns 1000 as "ubuntu", and useradd
# fails the build on that collision.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin sandbox

RUN mkdir -p /work && chmod 1777 /work

WORKDIR /work
USER 10001:10001

ENV HOME=/tmp

# Overridden per invocation: compile then run, or compile to assembly.
ENTRYPOINT ["/bin/sh", "-c"]
