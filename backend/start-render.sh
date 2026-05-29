#!/bin/sh
# Exit immediately if a command exits with a non-zero status
set -e

echo "Applying Django Database Migrations..."
# Extract database host for deployment side logging (masking credentials)
DB_HOST_LOG=$(echo "$DATABASE_URL" | sed -E 's/postgres:\/\/[^@]+@/postgres:\/\/*****@/')
echo "Connecting to database: $DB_HOST_LOG"
python manage.py makemigrations api --noinput
python manage.py migrate --noinput

echo "Starting Gunicorn Server on port $PORT..."
gunicorn core.wsgi:application --bind 0.0.0.0:$PORT
