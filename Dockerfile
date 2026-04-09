# Use official Python runtime as base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Verify data files are present (CRITICAL FOR DEBUGGING)
RUN echo "========================================" && \
    echo "VERIFYING DATA FILES..." && \
    echo "========================================" && \
    python verify_data_files.py || true && \
    echo "========================================" && \
    echo "Listing /app/data directory:" && \
    ls -lah /app/data/ 2>/dev/null || echo "❌ /app/data/ not found" && \
    echo "========================================" && \
    echo "Listing /app/api/data directory:" && \
    ls -lah /app/api/data/ 2>/dev/null || echo "❌ /app/api/data/ not found" && \
    echo "========================================" && \
    echo "All CSV files in /app:" && \
    find /app -name "*.csv" -type f -exec ls -lh {} \; 2>/dev/null || echo "❌ No CSV files found" && \
    echo "========================================"

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Create a non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Run the application with gunicorn
CMD exec gunicorn influBridge.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 4 \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
