# Sandbox image for untrusted Java submissions.
FROM eclipse-temurin:21-jdk-noble

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin sandbox

RUN mkdir -p /work && chmod 1777 /work

WORKDIR /work
USER 1000:1000

# The JVM writes its hsperfdata and temp files under HOME; point it at the
# tmpfs so the rest of the filesystem can stay untouched.
ENV HOME=/tmp \
    JAVA_TOOL_OPTIONS="-XX:-UsePerfData"

ENTRYPOINT ["/bin/sh", "-c"]
