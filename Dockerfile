FROM python:3.11-slim

# Create a non-root user to run the application
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install system dependencies (for mysql-connector-python)
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    default-mysql-client \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories and set ownership
RUN mkdir -p logs dumps static/admin_root && chown -R appuser:appuser /app

# Run Django migrations and collect static files at build time
# (ENV vars must be provided at runtime — see docker-compose.yml)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

# Expose the app port
EXPOSE 8000

# Healthcheck — maps to /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run migrations first, then start the app
# --proxy-headers: trust X-Forwarded-For from nginx so rate limiter sees real client IPs
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && python create_superuser.py && uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers"]
