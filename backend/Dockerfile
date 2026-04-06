# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
ENV PNPM_HOME=/pnpm
ENV PATH=${PNPM_HOME}:${PATH}

RUN corepack enable

# 先复制锁文件，确保依赖缓存层可复用；依赖变化时自动失效并重装
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN --mount=type=cache,id=lui-pnpm-store,target=/pnpm/store \
    pnpm install --frozen-lockfile

# 再复制源码，源码变化仅触发 build，不触发依赖重装
COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim AS backend-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

# requirements.txt 不变时复用 pip 缓存；变化时自动重解依赖
COPY backend/requirements.txt ./requirements.txt
RUN --mount=type=cache,id=lui-pip-cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY backend/ ./
COPY --from=frontend-builder /app/frontend/dist ./frontend_dist

RUN mkdir -p /app/workspace

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
