#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

# Replace Nginx port placeholder with the actual Render port (defaults to 80 or 8080 if not set)
PORT=${PORT:-80}
echo "Configuring Nginx to listen on port $PORT..."
sed -i "s/PORT_PLACEHOLDER/$PORT/g" /etc/nginx/sites-available/default

# Set internal fallbacks for Database and Redis URL since we are running locally inside the same container
export DATABASE_URL=${DATABASE_URL:-postgres://postgres:postgres@127.0.0.1:5432/hr_db}
export REDIS_URL=${REDIS_URL:-redis://127.0.0.1:6379/0}
export CELERY_TASK_ALWAYS_EAGER=${CELERY_TASK_ALWAYS_EAGER:-True}

# --- PostgreSQL Setup ---
echo "Initializing PostgreSQL..."
# Make sure the PGDATA directory exists and is owned by postgres
mkdir -p /var/lib/postgresql/data
chown -R postgres:postgres /var/lib/postgresql/data

# Initialize DB cluster if not already done
if [ ! -d "/var/lib/postgresql/data/base" ]; then
    su - postgres -c "/usr/lib/postgresql/15/bin/initdb -D /var/lib/postgresql/data"
fi

# Start PostgreSQL service locally (with low memory optimizations for 512MB RAM limit)
echo "Starting PostgreSQL with low-memory configuration..."
su - postgres -c "/usr/lib/postgresql/15/bin/pg_ctl -D /var/lib/postgresql/data -o '-c listen_addresses=127.0.0.1 -c max_connections=10 -c shared_buffers=16MB -c work_mem=1MB -c maintenance_work_mem=8MB -c temp_buffers=8MB' -l /var/lib/postgresql/data/logfile start"

# Wait for PostgreSQL to start
until su - postgres -c "pg_isready" 2>/dev/null; do
    echo "Waiting for PostgreSQL to be ready..."
    sleep 1
done

# Create user and database if they don't exist
echo "Setting up database user and db..."
su - postgres -c "psql -c \"CREATE USER postgres WITH SUPERUSER PASSWORD 'postgres';\"" || true
su - postgres -c "psql -c \"CREATE DATABASE hr_db OWNER postgres;\"" || true

# --- Redis Setup ---
if [ "$CELERY_TASK_ALWAYS_EAGER" != "True" ]; then
    echo "Starting Redis..."
    redis-server --daemonize yes
else
    echo "Skipping Redis startup (Running in low-memory Eager Celery mode)..."
fi

# --- Django Setup ---
echo "Running Django migrations..."
# Extract database host for deployment side logging (masking credentials)
DB_HOST_LOG=$(echo "$DATABASE_URL" | sed -E 's/postgres:\/\/[^@]+@/postgres:\/\/*****@/')
echo "Connecting to database: $DB_HOST_LOG"
cd /app/backend
python manage.py makemigrations api --noinput
python manage.py migrate --noinput

# Seed database automatically if requested
if [ "$SEED_DB" = "True" ]; then
    echo "Seeding database with default mock data..."
    python manage.py seed_db
fi

# --- Start Supervisor to manage processes ---
echo "Launching Nginx, Django Gunicorn, and Celery Worker via Supervisor..."
exec supervisord -n -c /etc/supervisor/conf.d/supervisord.conf
