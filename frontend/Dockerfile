# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# SecureVoice AI — web tier: builds the Vite/React app, serves it with Nginx
# and reverse-proxies /api (REST + WebSocket) to the FastAPI backend.
# ---------------------------------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=5 \
    CMD wget -qO- http://127.0.0.1/api/v1/health >/dev/null 2>&1 || exit 1
CMD ["nginx", "-g", "daemon off;"]
