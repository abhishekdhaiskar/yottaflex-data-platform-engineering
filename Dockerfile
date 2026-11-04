# Stage 1: Build environment
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies required for building certain packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies into a local user directory
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime environment
FROM python:3.12-slim

WORKDIR /app

# Install runtime system libraries (e.g., libpq for PostgreSQL bindings)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq \
    && rm -rf /var/lib/apt/lists/*

# Copy installed python packages from builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy source code and configuration files
COPY . .

# Install the local qpipe package in editable/normal mode
RUN pip install --no-cache-dir -e .

# Default command to run the pipeline or entrypoint
ENTRYPOINT ["python", "-m", "qpipe"]