#!/bin/bash

# ClaryAI Deployment Script
# This script automates the deployment of ClaryAI to production

set -e

# Configuration
DOCKER_HUB_USERNAME="claryai"
DOCKER_HUB_REPO="claryai"
VERSION=$(grep -oP 'version="\K[^"]+' setup.py)
TIMESTAMP=$(date +%Y%m%d%H%M%S)
TAG="${VERSION}-${TIMESTAMP}"
SLIM_TAG="${VERSION}-slim-${TIMESTAMP}"
WORKER_TAG="${VERSION}-worker-${TIMESTAMP}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print banner
echo -e "${GREEN}"
echo "====================================================="
echo "  ClaryAI Deployment Script"
echo "  Version: ${VERSION}"
echo "  Timestamp: ${TIMESTAMP}"
echo "====================================================="
echo -e "${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! docker-compose --version > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker Compose is not installed.${NC}"
    exit 1
fi

# Create necessary directories
echo -e "${YELLOW}Creating necessary directories...${NC}"
mkdir -p data nginx/conf.d nginx/ssl nginx/www/static

# Generate self-signed SSL certificate if not exists
if [ ! -f nginx/ssl/claryai.crt ] || [ ! -f nginx/ssl/claryai.key ]; then
    echo -e "${YELLOW}Generating self-signed SSL certificate...${NC}"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout nginx/ssl/claryai.key \
        -out nginx/ssl/claryai.crt \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=claryai.example.com"
fi

# Build Docker images
echo -e "${YELLOW}Building Docker images...${NC}"
docker-compose build

# Tag Docker images
echo -e "${YELLOW}Tagging Docker images...${NC}"
docker tag claryai/claryai:latest ${DOCKER_HUB_USERNAME}/${DOCKER_HUB_REPO}:${TAG}
docker tag claryai/claryai:latest ${DOCKER_HUB_USERNAME}/${DOCKER_HUB_REPO}:latest
docker tag claryai/claryai:slim ${DOCKER_HUB_USERNAME}/${DOCKER_HUB_REPO}:${SLIM_TAG}
docker tag claryai/claryai:slim ${DOCKER_HUB_USERNAME}/${DOCKER_HUB_REPO}:slim
docker tag claryai/claryai:worker ${DOCKER_HUB_USERNAME}/${DOCKER_HUB_REPO}:${WORKER_TAG}
docker tag claryai/claryai:worker ${DOCKER_HUB_USERNAME}/${DOCKER_HUB_REPO}:worker

# Login to Docker Hub
echo -e "${YELLOW}Logging in to Docker Hub...${NC}"
echo "Please enter your Docker Hub credentials:"
docker login

# Push Docker images
echo -e "${YELLOW}Pushing Docker images to Docker Hub...${NC}"
docker push ${DOCKER_HUB_USERNAME}/${DOCKER_HUB_REPO}:${TAG}
docker push ${DOCKER_HUB_USERNAME}/${DOCKER_HUB_REPO}:latest
docker push ${DOCKER_HUB_USERNAME}/${DOCKER_HUB_REPO}:${SLIM_TAG}
docker push ${DOCKER_HUB_USERNAME}/${DOCKER_HUB_REPO}:slim
docker push ${DOCKER_HUB_USERNAME}/${DOCKER_HUB_REPO}:${WORKER_TAG}
docker push ${DOCKER_HUB_USERNAME}/${DOCKER_HUB_REPO}:worker

# Start the services
echo -e "${YELLOW}Starting services...${NC}"
docker-compose up -d

# Wait for services to start
echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 10

# Check if services are running
echo -e "${YELLOW}Checking if services are running...${NC}"
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}Services are running!${NC}"
else
    echo -e "${RED}Error: Services failed to start.${NC}"
    docker-compose logs
    exit 1
fi

# Print success message
echo -e "${GREEN}"
echo "====================================================="
echo "  ClaryAI Deployment Successful!"
echo "  Version: ${VERSION}"
echo "  Tag: ${TAG}"
echo "  Access the API at: https://claryai.example.com"
echo "====================================================="
echo -e "${NC}"

exit 0
