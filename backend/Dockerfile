FROM python:3.12-slim

# Set Playwright browser path to a shared directory
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

# Create a non-root user (UID 1000 is required by Hugging Face Spaces)
RUN useradd -m -u 1000 user

WORKDIR /app

# Install system dependencies needed for compiling postgres drivers (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn psycopg2-binary

# Install Playwright browsers to the shared path and configure permissions
RUN mkdir -p /opt/playwright-browsers && \
    playwright install --with-deps chromium && \
    chown -R user:user /opt/playwright-browsers

# Copy application code and ensure ownership is set to the non-root user
COPY --chown=user:user . .

# Set up environment home directory for the user
ENV HOME=/home/user
USER user

# Expose ports for both local development and Hugging Face standard
EXPOSE 5000
EXPOSE 7860

# Start Flask using gunicorn dynamically listening to PORT env var (defaults to 5000)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --timeout 120 --workers 1 run:app"]

