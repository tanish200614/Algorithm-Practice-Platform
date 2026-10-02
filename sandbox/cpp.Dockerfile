# Sandbox image for untrusted C++ submissions.
#
# Has a compiler because submissions are compiled inside the sandbox too, so
# a nasty #include or compile-time bomb never touches the host.
FROM gcc:13-bookworm

# High uid so it doesn't clash with an existing user in the base image
# (eclipse-temurin already has 1000 as "ubuntu" and useradd fails on it).
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin sandbox

RUN mkdir -p /work && chmod 1777 /work

WORKDIR /work
USER 10001:10001

ENV HOME=/tmp

# Overridden per invocation: compile then run, or compile to assembly.
ENTRYPOINT ["/bin/sh", "-c"]
