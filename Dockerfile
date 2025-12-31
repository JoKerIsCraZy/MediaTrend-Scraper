FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (for lxml, etc.)
# Chromium for Selenium headless browser
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files and set ownership
COPY --chown=appuser:appuser . .

# Ensure the appuser has write permissions to the directory (important for creating .tmp files)
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Port for Web UI
EXPOSE 9000

# Environment variables (can be overridden)
ENV MEDIATREND_HOST=0.0.0.0
ENV MEDIATREND_PORT=9000

# Start command
CMD ["python", "main.py"]
