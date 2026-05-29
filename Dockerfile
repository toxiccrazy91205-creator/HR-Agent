FROM python:3.10-slim-bookworm

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies, PostgreSQL 15, Redis, Nginx, and Supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    postgresql-15 \
    postgresql-client-15 \
    redis-server \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Set up Postgres environment
ENV PGDATA=/var/lib/postgresql/data
RUN mkdir -p /var/run/postgresql && chown -R postgres:postgres /var/run/postgresql

WORKDIR /app

# Copy and install backend dependencies
COPY backend/requirements.txt /app/backend/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/backend/requirements.txt

# Download spaCy English dictionary
RUN python -m spacy download en_core_web_sm

# Pre-download and cache sentence-transformers model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy backend files
COPY backend /app/backend

# Copy frontend files to Nginx default html dir
COPY frontend /usr/share/nginx/html

# Copy nginx config to sites-available
COPY nginx.render.conf /etc/nginx/sites-available/default
RUN rm -f /etc/nginx/sites-enabled/default && ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Create data and media folders with proper permissions
RUN mkdir -p /app/backend/media /app/backend/data \
    && chmod -R 777 /app/backend/media /app/backend/data

# Copy supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy unified startup script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Entrypoint script starts postgres, redis, runs migrations/seeds, and launches supervisor
ENTRYPOINT ["/app/entrypoint.sh"]
