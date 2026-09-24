# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html tsconfig.json tsconfig.node.json vite.config.ts tailwind.config.cjs postcss.config.cjs ./
COPY src/ src/
COPY public/ public/

RUN npm run build

# Stage 2: Backend + serve static frontend
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for opencv-python-headless and scikit-image
# Note: libgl1-mesa-glx replaced by libgl1 in Debian 12+
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./

# Copy built frontend into static directory
COPY --from=frontend-build /app/dist ./static

# Create non-root user for security (P0 fix)
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Configure environment for production
ENV ENVIRONMENT=production
ENV LOG_LEVEL=INFO
ENV LOG_FORMAT=json
ENV HOST=0.0.0.0
ENV PORT=8000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/api/health')"

# Run with uvicorn (uses $PORT env var for PaaS compatibility, defaults to 8000)
# Request telemetry (main.py) replaces uvicorn's plain-text access log.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log
