FROM python:3.12-slim

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

# Copy backend files
COPY . .

# Expose port 5000
EXPOSE 5000

# Start Flask using gunicorn dynamically listening to PORT env var (defaults to 5000)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} run:app"]
