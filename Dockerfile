FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency file first for better caching
COPY pyproject.toml .

# Install dependencies using uv
RUN uv pip install --system -r pyproject.toml

# Copy source code
COPY src/ ./src/

# Create data directory for database
RUN mkdir -p /app/data

# Run with unbuffered output for live logging
CMD ["python", "-u", "-m", "src.main"]
