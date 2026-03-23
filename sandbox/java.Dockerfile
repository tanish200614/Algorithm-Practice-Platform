# Sandbox image for untrusted Java submissions.
FROM eclipse-temurin:21-jdk-noble

# A high uid so it cannot collide with a user the base image already
# ships — the eclipse-temurin base owns 1000 as "ubuntu", and useradd
# fails the build on that collision.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin sandbox

RUN mkdir -p /work && chmod 1777 /work

WORKDIR /work
USER 10001:10001

# The JVM writes its hsperfdata and temp files under HOME; point it at the
# tmpfs so the rest of the filesystem stays untouched.
#
# JVM flags are passed on the command line rather than through
# JAVA_TOOL_OPTIONS, because the JVM announces that variable on stderr and the
# UI would render the notice as a compile/runtime error.
ENV HOME=/tmp

ENTRYPOINT ["/bin/sh", "-c"]
