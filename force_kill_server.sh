#!/bin/bash
# Aggressive script to kill ALL processes using port 8000

echo "🔥 FORCE KILLING ALL PROCESSES ON PORT 8000 🔥"

# Get all PIDs using port 8000
PIDS=$(lsof -ti:8000 2>/dev/null)

if [ -n "$PIDS" ]; then
    echo "Found processes using port 8000: $PIDS"
    
    for PID in $PIDS; do
        echo "Force killing PID: $PID"
        kill -9 $PID 2>/dev/null
        sleep 1
    done
    
    # Double check with fuser
    echo "Using fuser to kill any remaining processes..."
    fuser -k 8000/tcp 2>/dev/null || true
    
    # Triple check with sudo fuser
    echo "Using sudo fuser as backup..."
    sudo fuser -k 8000/tcp 2>/dev/null || true
    
else
    echo "No processes found using port 8000"
fi

# Wait and verify
sleep 2

if lsof -i:8000 >/dev/null 2>&1; then
    echo "❌ Port 8000 is STILL in use:"
    lsof -i:8000
    echo ""
    echo "Trying nuclear option - killing ALL Python processes..."
    pkill -9 python
    sleep 2
    
    if lsof -i:8000 >/dev/null 2>&1; then
        echo "❌ STILL RUNNING! You may need to restart your machine."
        lsof -i:8000
    else
        echo "✅ Port 8000 is now free!"
    fi
else
    echo "✅ Port 8000 is now free!"
fi