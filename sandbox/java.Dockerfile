# Sandbox image for untrusted Java submissions.
FROM eclipse-temurin:21-jdk-noble

# High uid so it doesn't clash with an existing user in the base image
# (eclipse-temurin already has 1000 as "ubuntu" and useradd fails on it).
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin sandbox

RUN mkdir -p /work && chmod 1777 /work

WORKDIR /work
USER 10001:10001

# The JVM writes hsperfdata and temp files under HOME, so point it at the tmpfs.
#
# JVM flags go on the command line instead of JAVA_TOOL_OPTIONS, because the
# JVM prints a notice about that variable on stderr and the UI shows it as an
# error.
ENV HOME=/tmp

ENTRYPOINT ["/bin/sh", "-c"]
