#!/bin/bash

# Test script for the load balancer
# This script starts multiple mock target servers and the load balancer for testing

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

echo -e "${GREEN}All mock target servers started.${NC}"
echo -e "${YELLOW}Load balancer should be running in a container.${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all mock servers${NC}"
echo ""

# Cleanup function to kill mock servers
cleanup() {
    echo -e "\n${RED}Stopping mock target servers...${NC}"
    kill $MOCK1_PID $MOCK2_PID $MOCK3_PID 2>/dev/null
    wait $MOCK1_PID $MOCK2_PID $MOCK3_PID 2>/dev/null
    echo -e "${GREEN}All servers stopped.${NC}"
    exit 0
}

# Set up trap to call cleanup on script exit or interrupt
trap cleanup EXIT INT TERM

# Keep script running until interrupted
wait

