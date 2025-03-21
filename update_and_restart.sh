#!/bin/bash
# Script to update the code and restart the Video Scene Detector API service

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Path to project directory
PROJECT_DIR="/home/jason/Documents/VideoSceneDetector"

# Check if running as root, if not, use sudo
if [ "$EUID" -ne 0 ]; then
    USE_SUDO=sudo
else
    USE_SUDO=""
fi

echo -e "${YELLOW}Updating Video Scene Detector API and restarting service...${NC}"

# Change to project directory
cd $PROJECT_DIR || {
    echo -e "${RED}Failed to change to project directory: $PROJECT_DIR${NC}"
    exit 1
}

# If this is a git repository, pull latest changes
if [ -d .git ]; then
    echo -e "${YELLOW}Updating code from git repository...${NC}"
    git pull
    if [ $? -ne 0 ]; then
        echo -e "${RED}Git pull failed. Please resolve any conflicts manually.${NC}"
        exit 1
    fi
    echo -e "${GREEN}Code updated successfully!${NC}"
else
    echo -e "${YELLOW}Not a git repository, skipping code update.${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate || {
    echo -e "${RED}Failed to activate virtual environment. Please check if it exists.${NC}"
    exit 1
}

# Update dependencies
echo -e "${YELLOW}Updating dependencies...${NC}"
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to update dependencies.${NC}"
    exit 1
fi

# Stop the service
echo -e "${YELLOW}Stopping service...${NC}"
$USE_SUDO systemctl stop videoscenedetector.service
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to stop the service. Check if it exists and if you have permission.${NC}"
    exit 1
fi

# Optional: Give the service a moment to fully stop
sleep 2

# Restart the service
echo -e "${YELLOW}Starting service...${NC}"
$USE_SUDO systemctl start videoscenedetector.service
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to start the service.${NC}"
    echo -e "${YELLOW}Checking for errors:${NC}"
    $USE_SUDO journalctl -u videoscenedetector.service -n 20 --no-pager
    exit 1
fi

# Check status
echo -e "${YELLOW}Checking service status:${NC}"
$USE_SUDO systemctl status videoscenedetector.service --no-pager
if [ $? -ne 0 ]; then
    echo -e "${RED}Service is not running properly.${NC}"
    echo -e "${YELLOW}Checking for errors:${NC}"
    $USE_SUDO journalctl -u videoscenedetector.service -n 20 --no-pager
    exit 1
fi

# Service seems to be running, check if it's responding
echo -e "${YELLOW}Testing API health endpoint...${NC}"
HEALTH_CHECK=$(curl -s http://localhost:8000/api/v1/health || echo "Connection failed")

if [[ $HEALTH_CHECK == *"healthy"* ]]; then
    echo -e "${GREEN}API is running and healthy!${NC}"
else
    echo -e "${RED}API health check failed. Response: ${NC}"
    echo $HEALTH_CHECK
    echo -e "${YELLOW}Checking logs:${NC}"
    $USE_SUDO journalctl -u videoscenedetector.service -n 20 --no-pager
    exit 1
fi

echo -e "${GREEN}Update and restart completed successfully!${NC}"
exit 0 