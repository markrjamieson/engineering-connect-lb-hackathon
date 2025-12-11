#!/bin/bash

# Setup script for sticky session demonstration
# This script sets up the environment variables and starts mock targets
# for testing sticky session load balancing

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up Sticky Session Configuration${NC}"
echo "=========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Activate virtual environment if it exists
if [ -f "$PARENT_DIR/bin/activate" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source "$PARENT_DIR/bin/activate"
fi

# Export configuration for sticky sessions
export LISTENER_PORT=8080
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=STICKY
export SESSION_TTL=10000  # 10 seconds for testing (in milliseconds)

# Target Group 1: Backend servers (3 servers for load balancing)
export TARGET_GROUP_1_NAME=backend
export TARGET_GROUP_1_TARGETS=127.0.0.1:8081,127.0.0.1:8082,127.0.0.1:8083

# Listener Rule 1: Default route
export LISTENER_RULE_1_PATH_PREFIX=/
export LISTENER_RULE_1_PATH_REWRITE=
export LISTENER_RULE_1_TARGET_GROUP=backend

echo -e "${GREEN}Configuration exported.${NC}"
echo "  - Load Balancing Algorithm: STICKY"
echo "  - Session TTL: ${SESSION_TTL}ms (10 seconds)"
echo "  - Target Group: backend (ports 8081, 8082, 8083)"
echo ""

# Determine Python command (use python from venv if activated, otherwise python3 or python)
if command -v python &> /dev/null; then
    PYTHON_CMD="python"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo -e "${RED}Error: Python not found. Please install Python.${NC}"
    exit 1
fi

# Start mock target servers
echo -e "${YELLOW}Starting mock target servers...${NC}"
cd "$SCRIPT_DIR" || exit 1

$PYTHON_CMD mock_target.py 8081 &
MOCK1_PID=$!
$PYTHON_CMD mock_target.py 8082 &
MOCK2_PID=$!
$PYTHON_CMD mock_target.py 8083 &
MOCK3_PID=$!

# Wait for servers to start
sleep 2

echo -e "${GREEN}Mock target servers started!${NC}"
echo "  - Server 1: port 8081 (PID: $MOCK1_PID)"
echo "  - Server 2: port 8082 (PID: $MOCK2_PID)"
echo "  - Server 3: port 8083 (PID: $MOCK3_PID)"
echo ""

# Start load balancer
echo -e "${YELLOW}Starting load balancer on port 8080...${NC}"
cd "$PARENT_DIR" || exit 1
$PYTHON_CMD app.py &
LB_PID=$!

# Wait for load balancer to start
sleep 2

echo ""
echo -e "${GREEN}Load balancer started!${NC}"
echo ""
echo -e "${YELLOW}Configuration Summary:${NC}"
echo "  - Load Balancer: http://localhost:8080"
echo "  - Backend Servers: ports 8081, 8082, 8083"
echo "  - Session TTL: ${SESSION_TTL}ms"
echo ""
echo -e "${YELLOW}Test the sticky sessions with:${NC}"
echo "  ./test_sticky_sessions.sh"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Cleanup function
cleanup() {
    echo -e "\n${RED}Stopping all servers...${NC}"
    # Stop load balancer
    if [ ! -z "$LB_PID" ]; then
        kill $LB_PID 2>/dev/null
        wait $LB_PID 2>/dev/null
    fi
    # Stop mock target servers
    kill $MOCK1_PID $MOCK2_PID $MOCK3_PID 2>/dev/null
    wait $MOCK1_PID $MOCK2_PID $MOCK3_PID 2>/dev/null
    echo -e "${GREEN}All servers stopped.${NC}"
    exit 0
}

# Set up trap
trap cleanup EXIT INT TERM

# Keep script running
wait

