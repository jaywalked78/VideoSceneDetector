#!/bin/bash
# Script to kill the FastAPI server and all related processes

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}==================================================${NC}"
echo -e "${RED}Stopping Video Scene Detector API Server${NC}"
echo -e "${YELLOW}==================================================${NC}"

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
                echo -e "${RED}Killing process ${PID}...${NC}"
                kill -9 $PID 2>/dev/null || sudo kill -9 $PID 2>/dev/null || true
            done
            echo -e "${GREEN}Killed all processes using port ${PORT}${NC}"
        else
            echo -e "${GREEN}No processes found using port ${PORT}${NC}"
        fi
    fi
}

# Stop uvicorn processes by name
echo -e "${YELLOW}Stopping uvicorn processes...${NC}"
pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true
pkill -9 -f "python -m uvicorn app.main:app" 2>/dev/null || true
pkill -9 -f "uvicorn.*8000" 2>/dev/null || true

# Stop any VideoSceneDetector Python processes
echo -e "${YELLOW}Stopping VideoSceneDetector processes...${NC}"
pkill -9 -f "VideoSceneDetector" 2>/dev/null || true

# Kill processes using port 8000
kill_port_processes 8000

# Kill any remaining Python processes that might be related
echo -e "${YELLOW}Checking for remaining Python processes...${NC}"
PYTHON_PIDS=$(ps aux | grep -E "python.*app\.main|python.*uvicorn" | grep -v grep | awk '{print $2}' 2>/dev/null || true)

if [ -n "$PYTHON_PIDS" ]; then
    echo -e "${RED}Found related Python processes: ${PYTHON_PIDS}${NC}"
    for PID in $PYTHON_PIDS; do
        echo -e "${RED}Killing Python process ${PID}...${NC}"
        kill -9 $PID 2>/dev/null || true
    done
fi

# Wait a moment and check if port is free
sleep 2

# Final verification
if lsof -i:8000 >/dev/null 2>&1; then
    echo -e "${RED}Warning: Port 8000 is still in use${NC}"
    echo -e "${YELLOW}Remaining processes on port 8000:${NC}"
    lsof -i:8000 2>/dev/null || true
    
    # Last resort - kill anything on port 8000
    echo -e "${RED}Forcefully killing remaining processes on port 8000...${NC}"
    fuser -k 8000/tcp 2>/dev/null || true
    
else
    echo -e "${GREEN}✓ Port 8000 is now free${NC}"
fi

# Show any remaining related processes
echo -e "${YELLOW}Checking for any remaining processes...${NC}"
REMAINING=$(ps aux | grep -E "(uvicorn|VideoSceneDetector)" | grep -v grep 2>/dev/null || true)

if [ -n "$REMAINING" ]; then
    echo -e "${YELLOW}Remaining related processes:${NC}"
    echo "$REMAINING"
else
    echo -e "${GREEN}✓ All server processes have been stopped${NC}"
fi

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}Server shutdown complete!${NC}"
echo -e "${GREEN}==================================================${NC}"