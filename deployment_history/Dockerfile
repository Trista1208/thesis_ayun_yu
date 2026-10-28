# React web app (production build for Railway / Docker)
FROM node:20-alpine AS web-build
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# FastAPI + static SPA
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/
COPY backend/ backend/
COPY knowledge/ knowledge/
COPY --from=web-build /app/web/dist web/dist

ENV PORT=8000
EXPOSE 8000

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
