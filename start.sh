#!/bin/bash
# start.sh
# This script boots the 3 essential services required for the Render deployment

echo "Starting Redis server in the background..."
redis-server --daemonize yes

echo "Waiting for Redis to be ready..."
sleep 2

echo "Starting Celery worker in the background..."
# We run celery with 1 concurrency to strictly adhere to the 512MB RAM limit
/opt/venv/bin/celery -A backend.worker worker -Q fast_queue,slow_queue --loglevel=info --concurrency=1 &

echo "Starting FastAPI Web Server..."
# We run Uvicorn with 1 worker to strictly adhere to the 512MB RAM limit
# Render sets the PORT environment variable automatically
PORT=${PORT:-10000}
exec /opt/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 1
