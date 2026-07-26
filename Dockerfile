# ---- frontend build ----
FROM node:22-alpine AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- runtime ----
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    DB_PATH=/app/data/mail.db

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /fe/dist ./frontend/dist

RUN mkdir -p /app/data

EXPOSE 8080

# 单进程：内置探测调度器不可用多 worker
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
