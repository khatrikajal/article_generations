#!/bin/bash

# Article Generation System Startup Script
# This script handles the complete startup process for the application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Article Generation System...${NC}"

# Function to check if a service is running
check_service() {
    local service_name=$1
    local check_command=$2
    
    echo -n "Checking $service_name... "
    if eval $check_command > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${RED}✗${NC}"
        return 1
    fi
}

# Function to wait for service
wait_for_service() {
    local service_name=$1
    local check_command=$2
    local max_attempts=${3:-30}
    local attempt=1
    
    echo "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if eval $check_command > /dev/null 2>&1; then
            echo -e "${GREEN}$service_name is ready!${NC}"
            return 0
        fi
        
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    echo -e "${RED}$service_name failed to start within expected time${NC}"
    return 1
}

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found. Using environment variables or defaults.${NC}"
fi

# Load environment variables if .env exists
if [ -f .env ]; then
    source .env
fi

# Check required environment variables
required_vars=("SECRET_KEY" "POSTGRES_DB" "POSTGRES_USER" "POSTGRES_PASSWORD" "OPENAI_API_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo -e "${RED}Error: Missing required environment variables:${NC}"
    printf '%s\n' "${missing_vars[@]}"
    echo "Please set these variables in your .env file or environment."
    exit 1
fi

echo -e "${GREEN}Environment variables check passed.${NC}"

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo "Running in Docker container..."
    POSTGRES_HOST=${POSTGRES_HOST:-db}
    REDIS_HOST=${REDIS_HOST:-redis}
else
    echo "Running on host system..."
    POSTGRES_HOST=${POSTGRES_HOST:-localhost}
    REDIS_HOST=${REDIS_HOST:-localhost}
fi

# Wait for PostgreSQL
wait_for_service "PostgreSQL" "pg_isready -h $POSTGRES_HOST -p ${POSTGRES_PORT:-5432} -U $POSTGRES_USER"

# Wait for Redis
wait_for_service "Redis" "redis-cli -h $REDIS_HOST -p ${REDIS_PORT:-6379} ping | grep -q PONG"

# Create logs directory
mkdir -p logs

# Run Django migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Create superuser if it doesn't exist
echo "Checking for superuser..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
" 2>/dev/null || echo "Note: Could not create superuser automatically"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Check Celery workers (if not in web-only mode)
if [ "$1" != "web-only" ]; then
    echo "Starting Celery workers..."
    
    # Start Celery worker in background
    celery -A article_generation worker -l info --detach --pidfile=celery_worker.pid
    
    # Start Celery beat in background
    celery -A article_generation beat -l info --detach --pidfile=celery_beat.pid
    
    # Wait a moment for workers to start
    sleep 5
    
    # Check if Celery workers are responding
    if celery -A article_generation inspect ping > /dev/null 2>&1; then
        echo -e "${GREEN}Celery workers are running.${NC}"
    else
        echo -e "${YELLOW}Warning: Celery workers may not be responding properly.${NC}"
    fi
fi

# Test database connectivity
echo "Testing database connectivity..."
python manage.py shell -c "
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    print('Database connection: OK')
except Exception as e:
    print(f'Database connection error: {e}')
    exit(1)
"

# Test Redis connectivity
echo "Testing Redis connectivity..."
python manage.py shell -c "
from django.core.cache import cache
try:
    cache.set('test_key', 'test_value', 10)
    value = cache.get('test_key')
    if value == 'test_value':
        print('Redis connection: OK')
    else:
        raise Exception('Cache test failed')
except Exception as e:
    print(f'Redis connection error: {e}')
    exit(1)
"

# Test OpenAI API
echo "Testing OpenAI API..."
python manage.py shell -c "
import os
from openai import OpenAI
try:
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    # Just test the client initialization and a simple request
    models = client.models.list()
    print('OpenAI API: OK')
except Exception as e:
    print(f'OpenAI API error: {e}')
    print('Note: Article generation may not work properly')
"

echo -e "${GREEN}System startup checks completed successfully!${NC}"

# Start the appropriate service
if [ "$1" = "web" ] || [ "$1" = "web-only" ]; then
    echo "Starting Django development server..."
    python manage.py runserver 0.0.0.0:8000
elif [ "$1" = "worker" ]; then
    echo "Starting Celery worker..."
    celery -A article_generation worker -l info
elif [ "$1" = "beat" ]; then
    echo "Starting Celery beat..."
    celery -A article_generation beat -l info
elif [ "$1" = "flower" ]; then
    echo "Starting Celery Flower..."
    celery -A article_generation flower --port=5555
elif [ "$1" = "production" ]; then
    echo "Starting production server with Gunicorn..."
    gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 300 article_generation.wsgi:application
else
    echo -e "${GREEN}Startup completed successfully!${NC}"
    echo ""
    echo "Available commands:"
    echo "  $0 web         - Start Django development server"
    echo "  $0 web-only    - Start Django server without Celery"
    echo "  $0 worker      - Start Celery worker"
    echo "  $0 beat        - Start Celery beat scheduler"
    echo "  $0 flower      - Start Celery Flower monitoring"
    echo "  $0 production  - Start production server with Gunicorn"
    echo ""
    echo "System is ready for use!"
fi