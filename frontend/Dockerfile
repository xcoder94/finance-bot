# Chontak mini app (Vite build served by nginx, /api proxied to the API).
# Build context: repository root. Dockerfile location: /frontend/Dockerfile

FROM node:24-alpine AS builder

WORKDIR /app

# --legacy-peer-deps: @telegram-apps/telegram-ui 2.1.13 declares a React 18 peer,
# the project runs React 19 — same resolution as the local install.
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then \
        npm ci --legacy-peer-deps; \
    else \
        npm install --legacy-peer-deps; \
    fi

COPY frontend/ ./
RUN npm run build


FROM nginx:1.27-alpine

# BACKEND_URL — where /api/... is forwarded. No trailing slash.
# In Coolify this is the API service's internal URL, e.g. http://chontak-api:5001
ENV BACKEND_URL=http://api:5001

COPY frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz >/dev/null 2>&1 || exit 1
