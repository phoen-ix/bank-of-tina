FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (mariadb-client for mysqldump/mysql in backup/restore,
# gosu for dropping privileges in the entrypoint)
RUN apt-get update && apt-get install -y --no-install-recommends mariadb-client curl gosu && rm -rf /var/lib/apt/lists/*

# Create non-root user (rarely changes — cached early)
RUN groupadd -r -g 1000 appuser && useradd -r -u 1000 -g appuser -d /app -s /sbin/nologin appuser

# Install dependencies (changes infrequently)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entrypoint (rarely changes)
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create necessary directories
RUN mkdir -p /uploads /database /backups /app/static/icons

# Copy application code (changes frequently — last)
COPY app/ .

# Fix ownership after COPY
RUN chown -R appuser:appuser /app /uploads /backups /database

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

# Entrypoint fixes bind-mount ownership then drops to appuser
ENTRYPOINT ["/entrypoint.sh"]

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "300", "app:app"]
