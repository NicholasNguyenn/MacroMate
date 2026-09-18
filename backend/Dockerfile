# App Runner serves on 8080 by default and health-checks over HTTP.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependency layer first so code edits do not invalidate the install.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

# Stateless MCP so any instance can serve any request once App Runner scales
# past one container. See .env.example for the tradeoff.
ENV MACROMATE_MCP_STATELESS=true \
    MACROMATE_PORT=8080

EXPOSE 8080

# Single worker: the MCP session manager holds per-session state in process.
# Scale with App Runner instances, not workers.
CMD ["uvicorn", "macromate.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
