# syntax=docker/dockerfile:1

# -------------------------
# Builder stage
# -------------------------
FROM ghcr.io/astral-sh/uv:alpine AS builder

WORKDIR /app

# Install build deps (if needed for Python packages)
RUN apk add --no-cache build-base libffi-dev

# Install yt-dlp from Alpine repos
RUN apk add --no-cache yt-dlp

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install all Python dependencies with uv
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# -------------------------
# Runtime stage
# -------------------------
FROM ghcr.io/astral-sh/uv:alpine AS runner

WORKDIR /app

# Install runtime system dependencies (including yt-dlp)
RUN apk add --no-cache libffi yt-dlp

# Copy environment and code
COPY --from=builder /app /app

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Start FastAPI
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
