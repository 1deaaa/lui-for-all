FROM node:22-alpine

WORKDIR /app

# 锁定 pnpm 大版本，避免 corepack 拉取最新 pnpm11 导致与 Node 不兼容
# （本地已验证 pnpm@10.33.0 可用，故此处锁定同一版本）
RUN corepack enable && corepack prepare pnpm@10.33.0 --activate

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./

EXPOSE 5173

CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]
