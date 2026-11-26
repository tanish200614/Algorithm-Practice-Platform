# GitHub login service (Spring Boot).
#
# Built from the repo root or from auth-service/; only this directory is used.
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src

# Dependencies first so source edits don't redownload the world.
COPY pom.xml .
RUN mvn -B -q dependency:go-offline

COPY src ./src
RUN mvn -B -q package -DskipTests

FROM eclipse-temurin:21-jre

RUN useradd --uid 10002 --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data && chown app /data

COPY --from=build /src/target/auth-service.jar /app/auth-service.jar

USER app
# H2 file database on a volume, so users and roles survive a redeploy.
ENV AUTH_DB_URL=jdbc:h2:file:/data/auth \
    JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75 -XX:+UseSerialGC"

EXPOSE 8081
CMD ["java", "-jar", "/app/auth-service.jar"]
