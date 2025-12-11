#!/bin/bash

# Setup script for path-based routing demonstration
# This script sets up the environment variables and starts mock targets

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up Path-Based Routing Configuration${NC}"
echo "=========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment if it exists
if [ -f "$SCRIPT_DIR/bin/activate" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source "$SCRIPT_DIR/bin/activate"
fi

# Export configuration for path-based routing
export LISTENER_PORT=8080
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=ROUND_ROBIN

# Target Group 1: API Backend (2 servers for load balancing)
export TARGET_GROUP_1_NAME=api_backend
export TARGET_GROUP_1_TARGETS=127.0.0.1:8081,127.0.0.1:8082

# Target Group 2: Web Backend (2 servers for load balancing)
export TARGET_GROUP_2_NAME=web_backend
export TARGET_GROUP_2_TARGETS=127.0.0.1:8083,127.0.0.1:8084

# Target Group 3: Static Backend (1 server)
export TARGET_GROUP_3_NAME=static_backend
export TARGET_GROUP_3_TARGETS=127.0.0.1:8085

# Listener Rule 1: Route /api/* to api_backend
export LISTENER_RULE_1_PATH_PREFIX=/api
export LISTENER_RULE_1_PATH_REWRITE=/api
export LISTENER_RULE_1_TARGET_GROUP=api_backend

# Listener Rule 2: Route /web/* to web_backend
export LISTENER_RULE_2_PATH_PREFIX=/web
export LISTENER_RULE_2_PATH_REWRITE=/web
export LISTENER_RULE_2_TARGET_GROUP=web_backend

# Listener Rule 3: Route /static/* to static_backend
export LISTENER_RULE_3_PATH_PREFIX=/static
export LISTENER_RULE_3_PATH_REWRITE=/static
export LISTENER_RULE_3_TARGET_GROUP=static_backend

# Listener Rule 4: Default catch-all route (optional, for testing)
# export LISTENER_RULE_4_PATH_PREFIX=/
# export LISTENER_RULE_4_PATH_REWRITE=
# export LISTENER_RULE_4_TARGET_GROUP=api_backend

echo -e "${GREEN}Configuration exported. Starting mock target servers...${NC}"
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
echo -e "${YELLOW}Starting API backend servers (8081, 8082)...${NC}"
$PYTHON_CMD mock_target.py 8081 &
MOCK1_PID=$!
$PYTHON_CMD mock_target.py 8082 &
MOCK2_PID=$!

echo -e "${YELLOW}Starting Web backend servers (8083, 8084)...${NC}"
$PYTHON_CMD mock_target.py 8083 &
MOCK3_PID=$!
$PYTHON_CMD mock_target.py 8084 &
MOCK4_PID=$!

echo -e "${YELLOW}Starting Static backend server (8085)...${NC}"
$PYTHON_CMD mock_target.py 8085 &
MOCK5_PID=$!

# Wait for servers to start
sleep 2

echo ""
echo -e "${GREEN}All mock target servers started!${NC}"
echo ""

# Start load balancer
echo -e "${YELLOW}Starting load balancer on port 8080...${NC}"
$PYTHON_CMD app.py &
LB_PID=$!

# Wait for load balancer to start
sleep 2

echo ""
echo -e "${GREEN}Load balancer started!${NC}"
echo ""
echo -e "${YELLOW}Configuration Summary:${NC}"
echo "  - Load Balancer: http://localhost:8080"
echo "  - API Backend: ports 8081, 8082 (routes: /api/*)"
echo "  - Web Backend: ports 8083, 8084 (routes: /web/*)"
echo "  - Static Backend: port 8085 (routes: /static/*)"
echo ""
echo -e "${YELLOW}Test the load balancer with:${NC}"
echo "  ./test_path_based_routing.sh"
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
    kill $MOCK1_PID $MOCK2_PID $MOCK3_PID $MOCK4_PID $MOCK5_PID 2>/dev/null
    wait $MOCK1_PID $MOCK2_PID $MOCK3_PID $MOCK4_PID $MOCK5_PID 2>/dev/null
    echo -e "${GREEN}All servers stopped.${NC}"
    exit 0
}

# Set up trap
trap cleanup EXIT INT TERM

# Keep script running
wait

