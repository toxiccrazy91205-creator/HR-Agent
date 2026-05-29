#!/bin/sh
# Exit immediately if a command exits with a non-zero status
set -e

echo "Applying Django Database Migrations..."
python manage.py makemigrations api
python manage.py migrate

echo "Starting Celery Worker in the background..."
celery -A core worker -l info --concurrency=1 &

echo "Starting Gunicorn Server on port $PORT..."
gunicorn core.wsgi:application --bind 0.0.0.0:$PORT
