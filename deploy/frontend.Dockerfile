# Static frontend, built once and served by nginx.
#
# VITE_API_URL is baked in at build time as "/api", so the bundle always talks
# to its own origin. That means this image runs unchanged behind any hostname
# or load balancer — no per-environment rebuild.
FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
ENV VITE_API_URL=/api
RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/nginx.conf.template /etc/nginx/templates/default.conf.template

# Which host to proxy /api to; overridden per environment.
ENV BACKEND_HOST=backend
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# 127.0.0.1, not localhost: localhost resolves to ::1 in this image while
# nginx listens on IPv4 only, so the check refused the connection against a
# server that was serving fine.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
