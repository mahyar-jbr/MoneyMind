# MoneyMind — Railway deploy container (R4).
#
# Single container, two processes (backend on :8000, agent on :8001),
# matches the loopback contract from #4a (agent listens only on 127.0.0.1).
#
# Build context: repo root (so we can COPY both backend/ and agent/).
# Build:  docker build -t moneymind .
# Run:    docker run -p 8000:8000 --env-file .env moneymind
#
# Base: python 3.12 slim (Debian bookworm). Includes Node 20.19+ via NodeSource
# for #R1 MCP integration on Sunday (subprocess `npx mongodb-mcp-server`).

FROM python:3.12-slim-bookworm

# Install Node 20.19+ alongside Python.
# uv: official binary install (faster + matches local dev).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates supervisor \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

# Install backend deps first (better layer caching).
COPY backend/pyproject.toml backend/uv.lock /app/backend/
RUN cd /app/backend && uv sync --frozen --no-dev

# Install agent deps.
COPY agent/pyproject.toml agent/uv.lock /app/agent/
RUN cd /app/agent && uv sync --frozen --no-dev

# Copy source.
COPY backend /app/backend
COPY agent /app/agent

# Supervisor config and entrypoint.
COPY deploy/supervisord.conf /etc/supervisor/conf.d/moneymind.conf
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Railway sets $PORT for the *exposed* service. We pin backend to that port,
# agent to a fixed loopback port (8001).
ENV BACKEND_PORT=8000 \
    AGENT_HOST=127.0.0.1 \
    AGENT_PORT=8001 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
