# Sandbox image for untrusted C++ submissions.
#
# Carries a compiler because submissions are compiled inside the sandbox
# too — a hostile #include or a compile-time bomb should not reach the host.
FROM gcc:13-bookworm

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin sandbox

RUN mkdir -p /work && chmod 1777 /work

WORKDIR /work
USER 1000:1000

ENV HOME=/tmp

# Overridden per invocation: compile then run, or compile to assembly.
ENTRYPOINT ["/bin/sh", "-c"]
