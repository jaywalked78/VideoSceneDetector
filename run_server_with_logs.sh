#!/bin/bash
# Script to run the FastAPI server with live logging

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${GREEN}Starting Video Scene Detector API with live logging${NC}"
echo -e "${BLUE}==================================================${NC}"

# Set environment variable to enable debug mode
export DEBUG_MODE=true

# Set environment variables for unbuffered output
export FORCE_COLOR=1
export NODE_ENV=development

# Ensure terminal emulation is enabled for progress display
export TERM=xterm-256color

# Create logs directory if it doesn't exist
mkdir -p logs

# Define log file with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/server_${TIMESTAMP}.log"

echo "Starting server with progress display enabled..."
echo "Logs will be saved to: $LOG_FILE"

# Set environment variables for webhook notifications
if [ -z "$WEBHOOK_URL" ]; then
  export WEBHOOK_URL="http://localhost:3001/webhook/video-processing"
  echo -e "${YELLOW}Using default webhook URL: ${WEBHOOK_URL}${NC}"
  echo -e "${YELLOW}Set WEBHOOK_URL environment variable to change${NC}"
else
  echo -e "${GREEN}Using configured webhook URL: ${WEBHOOK_URL}${NC}"
fi

# Function to kill processes using a specific port
kill_port_processes() {
    local PORT=$1
    echo -e "${YELLOW}Checking for processes using port ${PORT}...${NC}"
    
    # Find processes using the port with lsof
    if command -v lsof >/dev/null 2>&1; then
        # Get all PIDs using the port
        PIDS=$(lsof -ti:${PORT} 2>/dev/null)
        
        if [ -n "$PIDS" ]; then
            echo -e "${RED}Found process(es) using port ${PORT}: ${PIDS}${NC}"
            for PID in $PIDS; do
                echo -e "${RED}Killing process ${PID} with SIGKILL...${NC}"
                kill -9 $PID 2>/dev/null || sudo kill -9 $PID 2>/dev/null || true
            done
            echo -e "${GREEN}Killed all processes using port ${PORT}${NC}"
            
            # Wait a moment to ensure the port is released
            sleep 2
        else
            echo -e "${GREEN}No processes found using port ${PORT}${NC}"
        fi
    fi
    
    # Try with netstat as a backup
    if command -v netstat >/dev/null 2>&1; then
        if netstat -tuln | grep -q ":${PORT} "; then
            echo -e "${YELLOW}Port ${PORT} still appears to be in use. Trying alternative methods...${NC}"
            
            # Use fuser if available
            if command -v fuser >/dev/null 2>&1; then
                echo -e "${YELLOW}Using fuser to kill processes on port ${PORT}...${NC}"
                sudo fuser -k ${PORT}/tcp 2>/dev/null || true
                sleep 2
            fi
        fi
    fi
    
    # Final verification
    if (command -v lsof >/dev/null 2>&1 && lsof -i:${PORT} >/dev/null 2>&1) || \
       (command -v netstat >/dev/null 2>&1 && netstat -tuln | grep -q ":${PORT} "); then
        echo -e "${RED}Warning: Port ${PORT} is still in use after multiple kill attempts${NC}"
        return 1
    fi
    
    echo -e "${GREEN}Port ${PORT} is now available${NC}"
    return 0
}

# Stop any running uvicorn processes first
echo -e "${YELLOW}Stopping any existing uvicorn processes...${NC}"
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "python -m uvicorn app.main:app" 2>/dev/null || true
sleep 2

# Then aggressively kill anything using port 8000
if ! kill_port_processes 8000; then
    echo -e "${RED}Failed to free port 8000 automatically.${NC}"
    echo -e "${YELLOW}Forcefully killing all Python processes (this might affect other applications)...${NC}"
    
    # Last resort - kill all Python processes (risky but effective)
    pkill -9 python || true
    sleep 3
    
    # Check one more time
    if ! kill_port_processes 8000; then
        echo -e "${RED}Port 8000 still in use. Please run these commands manually and try again:${NC}"
        echo -e "${YELLOW}sudo fuser -k 8000/tcp${NC}"
        echo -e "${YELLOW}sudo lsof -i:8000${NC}"
        exit 1
    fi
fi

# Activate virtual environment if present
if [ -d "venv" ]; then
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Start the FastAPI server with debug logging
echo -e "${GREEN}Starting FastAPI server with live logging on port 8000...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo -e "${BLUE}==================================================${NC}"

# Start uvicorn with debug log level
# Important: Don't redirect output for live logging
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug 

# Start the server with output going to both console and log file
# Using stdbuf to disable buffering
stdbuf -o0 -e0 node dist/main.js | tee -a "$LOG_FILE" 