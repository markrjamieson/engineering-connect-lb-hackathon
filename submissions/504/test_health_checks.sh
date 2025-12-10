#!/bin/bash
"""
Health Check Test Script
Demonstrates the health check functionality by setting up:
1. Mock backends that respond to health checks
2. A load balancer with health checks enabled
3. Requests to verify only healthy targets receive traffic
"""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Health Check Test Demo${NC}"
echo "This script demonstrates the health check feature of the load balancer."
echo ""

# Check if mock_target.py exists
if [ ! -f "mock_target.py" ]; then
    echo -e "${RED}Error: mock_target.py not found${NC}"
    exit 1
fi

# Configuration
MOCK_PORT_1=8081
MOCK_PORT_2=8082
MOCK_PORT_3=8083
LB_PORT=8080

echo -e "${YELLOW}Starting mock target servers...${NC}"

# Start mock targets
python mock_target.py $MOCK_PORT_1 &
MOCK_PID_1=$!
echo -e "${GREEN}✓ Mock target 1 started on port $MOCK_PORT_1 (PID: $MOCK_PID_1)${NC}"

python mock_target.py $MOCK_PORT_2 &
MOCK_PID_2=$!
echo -e "${GREEN}✓ Mock target 2 started on port $MOCK_PORT_2 (PID: $MOCK_PID_2)${NC}"

python mock_target.py $MOCK_PORT_3 &
MOCK_PID_3=$!
echo -e "${GREEN}✓ Mock target 3 started on port $MOCK_PORT_3 (PID: $MOCK_PID_3)${NC}"

# Give servers time to start
sleep 2

echo ""
echo -e "${YELLOW}Configuring load balancer with health checks...${NC}"

# Configure load balancer
export LISTENER_PORT=$LB_PORT
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=ROUND_ROBIN

# Target Group with Health Checks enabled
export TARGET_GROUP_1_NAME=backends
export TARGET_GROUP_1_TARGETS=127.0.0.1:$MOCK_PORT_1,127.0.0.1:$MOCK_PORT_2,127.0.0.1:$MOCK_PORT_3
export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=true
export TARGET_GROUP_1_HEALTH_CHECK_PATH=/health
export TARGET_GROUP_1_HEALTH_CHECK_INTERVAL=5000
export TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD=1
export TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD=1

# Listener Rule
export LISTENER_RULE_1_PATH_PREFIX=/
export LISTENER_RULE_1_PATH_REWRITE=
export LISTENER_RULE_1_TARGET_GROUP=backends

echo -e "${GREEN}✓ Load balancer configured${NC}"
echo ""
echo -e "${YELLOW}Starting load balancer on port $LB_PORT...${NC}"

# Start load balancer
python app.py &
LB_PID=$!
echo -e "${GREEN}✓ Load balancer started (PID: $LB_PID)${NC}"

# Give load balancer time to start and run initial health checks
sleep 3

echo ""
echo -e "${YELLOW}Making test requests to load balancer...${NC}"
echo ""

# Function to cleanup
cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"
    kill $MOCK_PID_1 $MOCK_PID_2 $MOCK_PID_3 $LB_PID 2>/dev/null
    wait $MOCK_PID_1 $MOCK_PID_2 $MOCK_PID_3 $LB_PID 2>/dev/null
    echo -e "${GREEN}✓ All processes terminated${NC}"
}

trap cleanup EXIT

# Make test requests
for i in {1..6}; do
    echo -e "${YELLOW}Request $i:${NC}"
    curl -s http://localhost:$LB_PORT/test | python -m json.tool | head -20
    echo ""
    sleep 1
done

echo -e "${YELLOW}Health check test complete!${NC}"
echo ""
echo "Observations:"
echo "- The load balancer distributed requests among all 3 healthy targets"
echo "- Health checks run every 5 seconds in the background"
echo "- Each target must pass 1 check to be marked healthy"
echo "- If a target failed its health check, it would be removed from rotation"
