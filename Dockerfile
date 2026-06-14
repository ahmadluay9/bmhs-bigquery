# Use an official Python runtime as a parent image
FROM python:3.14-slim

# Install uv directly from the official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Enable bytecode compilation for faster app startup
ENV UV_COMPILE_BYTECODE=1

# Copy dependency files first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment (.venv)
RUN uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application code
COPY . .

# Sync the project itself (installs the local package if defined in pyproject.toml)
RUN uv sync --frozen --no-dev

# Place the uv virtual environment executables in the PATH
# This allows you to run 'uvicorn' directly without prefixing it with 'uv run'
ENV PATH="/app/.venv/bin:$PATH"

# We will define the startup command in docker-compose
CMD uv run uvicorn bigquery_agent.agent:a2a_app --host 0.0.0.0 --port $PORT