#!/bin/bash

# Test script for the load balancer
# This script starts multiple mock target servers and the load balancer locally for testing

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Get the parent directory (where app.py is located)
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting mock target servers...${NC}"

# Start mock target servers in background (from tests directory)
cd "$SCRIPT_DIR"
python mock_target.py 8081 &
MOCK1_PID=$!
echo -e "${YELLOW}Mock target 1 started on port 8081 (PID: $MOCK1_PID)${NC}"

python mock_target.py 8082 &
MOCK2_PID=$!
echo -e "${YELLOW}Mock target 2 started on port 8082 (PID: $MOCK2_PID)${NC}"

python mock_target.py 8083 &
MOCK3_PID=$!
echo -e "${YELLOW}Mock target 3 started on port 8083 (PID: $MOCK3_PID)${NC}"

# Wait a moment for servers to start
sleep 2

echo -e "${GREEN}All mock target servers started.${NC}"

# Configure load balancer environment variables
export LISTENER_PORT=8080
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=ROUND_ROBIN

# Target Group 1: Backend servers
export TARGET_GROUP_1_NAME=backend
export TARGET_GROUP_1_TARGETS=127.0.0.1:8081,127.0.0.1:8082,127.0.0.1:8083

# Listener Rule 1: Root path routing
export LISTENER_RULE_1_PATH_PREFIX=/
export LISTENER_RULE_1_PATH_REWRITE=
export LISTENER_RULE_1_TARGET_GROUP=backend

export HEADER_CONVENTION_ENABLE=false

# Health Checks
export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=true
export TARGET_GROUP_1_HEALTH_CHECK_PATH=/health
export TARGET_GROUP_1_HEALTH_CHECK_INTERVAL=60000
export TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD=2
export TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD=3

echo -e "${GREEN}Starting load balancer locally with gunicorn...${NC}"
echo -e "${YELLOW}Load balancer will run on port 8080${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Start load balancer with gunicorn in background (from project root directory)
cd "$PROJECT_DIR"
gunicorn -w 4 -k gthread --threads 4 -b 0.0.0.0:8080 app:app &
APP_PID=$!
echo -e "${YELLOW}Load balancer started with gunicorn (PID: $APP_PID)${NC}"

# Wait a moment for load balancer to start
sleep 2

echo -e "${GREEN}All services started.${NC}"
echo -e "${YELLOW}Load balancer: http://localhost:8080${NC}"
echo -e "${YELLOW}Mock targets: http://localhost:8081, http://localhost:8082, http://localhost:8083${NC}"
echo ""

# Cleanup function to kill all servers
cleanup() {
    echo -e "\n${RED}Stopping all servers...${NC}"
    kill $MOCK1_PID $MOCK2_PID $MOCK3_PID $APP_PID 2>/dev/null
    wait $MOCK1_PID $MOCK2_PID $MOCK3_PID $APP_PID 2>/dev/null
    echo -e "${GREEN}All servers stopped.${NC}"
    exit 0
}

# Set up trap to call cleanup on script exit or interrupt
trap cleanup EXIT INT TERM

# Keep script running until interrupted
wait

