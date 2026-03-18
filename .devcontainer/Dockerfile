FROM mcr.microsoft.com/devcontainers/python:3.13-bullseye

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set uv environment variables
ENV UV_SYSTEM_PYTHON=0
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /workspace

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install dependencies (uv will download Python 3.14 as needed)
RUN uv sync --all-groups --frozen || true
