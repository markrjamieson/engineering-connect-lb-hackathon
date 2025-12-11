#!/bin/bash

# Setup script for sticky session load balancer
# This script starts multiple mock target servers and the load balancer with STICKY algorithm

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting mock target servers...${NC}"

# Start mock target servers in background
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

# Set up environment variables for load balancer with STICKY algorithm
export LISTENER_PORT=8080
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=STICKY
export SESSION_TTL=30000  # 30 seconds in milliseconds

# Target Group 1: Multiple targets
export TARGET_GROUP_1_NAME=backend
export TARGET_GROUP_1_TARGETS=127.0.0.1:8081,127.0.0.1:8082,127.0.0.1:8083

# Listener Rule 1: Root path
export LISTENER_RULE_1_PATH_PREFIX=/
export LISTENER_RULE_1_PATH_REWRITE=
export LISTENER_RULE_1_TARGET_GROUP=backend

echo -e "${GREEN}Starting load balancer on port 8080 with STICKY algorithm...${NC}"
echo -e "${BLUE}Configuration:${NC}"
echo -e "  ${BLUE}LOAD_BALANCING_ALGORITHM=${LOAD_BALANCING_ALGORITHM}${NC}"
echo -e "  ${BLUE}SESSION_TTL=${SESSION_TTL}ms${NC}"
echo -e "  ${BLUE}Targets: 127.0.0.1:8081, 127.0.0.1:8082, 127.0.0.1:8083${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Start load balancer (this will block)
python app.py

# Cleanup: Kill mock servers when load balancer stops
echo -e "\n${RED}Stopping mock target servers...${NC}"
kill $MOCK1_PID $MOCK2_PID $MOCK3_PID 2>/dev/null
wait $MOCK1_PID $MOCK2_PID $MOCK3_PID 2>/dev/null
echo -e "${GREEN}All servers stopped.${NC}"

