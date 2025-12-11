#!/bin/bash

# Test script for sticky session algorithm
# This script makes requests from different clients to verify sticky sessions work correctly

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

LB_URL="http://127.0.0.1:8080"

# Check if load balancer is running
echo -e "${YELLOW}Checking if load balancer is running...${NC}"
if ! curl -s --connect-timeout 2 "$LB_URL" > /dev/null 2>&1; then
    echo -e "${RED}Error: Load balancer is not running on $LB_URL${NC}"
    echo -e "${YELLOW}Please run ./setup_sticky_lb.sh first in another terminal${NC}"
    exit 1
fi
echo -e "${GREEN}Load balancer is running${NC}"
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Testing STICKY Load Balancing Algorithm${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to extract server port from response
extract_server_port() {
    local response="$1"
    echo "$response" | grep -o '"server_port":[0-9]*' | grep -o '[0-9]*'
}

# Function to make a request with a specific client IP
make_request() {
    local client_ip="$1"
    local request_num="$2"
    local response=$(curl -s -H "X-Forwarded-For: $client_ip" "$LB_URL/test?req=$request_num")
    local server_port=$(extract_server_port "$response")
    echo "$server_port"
}

# Test 1: Same client should get the same target
echo -e "${GREEN}Test 1: Same client should stick to the same target${NC}"
echo -e "${YELLOW}Making 5 requests from client 192.168.1.100...${NC}"

CLIENT1_IP="192.168.1.100"
ports=()
for i in {1..5}; do
    port=$(make_request "$CLIENT1_IP" "$i")
    ports+=("$port")
    echo -e "  Request $i -> Target server on port $port"
    sleep 0.5
done

# Check if all requests went to the same target
first_port="${ports[0]}"
all_same=true
for port in "${ports[@]}"; do
    if [ "$port" != "$first_port" ]; then
        all_same=false
        break
    fi
done

if [ "$all_same" = true ]; then
    echo -e "${GREEN}✓ PASS: All requests from same client went to the same target (port $first_port)${NC}"
else
    echo -e "${RED}✗ FAIL: Requests from same client went to different targets${NC}"
    echo -e "${RED}  Ports: ${ports[*]}${NC}"
fi
echo ""

# Test 2: Different clients can get different targets
echo -e "${GREEN}Test 2: Different clients can get different targets${NC}"
echo -e "${YELLOW}Making requests from 3 different clients...${NC}"

CLIENT2_IP="192.168.1.101"
CLIENT3_IP="192.168.1.102"

port1=$(make_request "$CLIENT1_IP" "1")
port2=$(make_request "$CLIENT2_IP" "1")
port3=$(make_request "$CLIENT3_IP" "1")

echo -e "  Client $CLIENT1_IP -> Target server on port $port1"
echo -e "  Client $CLIENT2_IP -> Target server on port $port2"
echo -e "  Client $CLIENT3_IP -> Target server on port $port3"

# Check if at least two different targets were used
unique_ports=$(echo "$port1 $port2 $port3" | tr ' ' '\n' | sort -u | wc -l)
if [ "$unique_ports" -ge 2 ]; then
    echo -e "${GREEN}✓ PASS: Different clients can be assigned to different targets${NC}"
else
    echo -e "${YELLOW}⚠ NOTE: All clients got the same target (this can happen with round-robin)${NC}"
fi
echo ""

# Test 3: Same client continues to get same target across multiple requests
echo -e "${GREEN}Test 3: Client persistence across multiple requests${NC}"
echo -e "${YELLOW}Making 10 requests from client $CLIENT2_IP...${NC}"

ports=()
for i in {1..10}; do
    port=$(make_request "$CLIENT2_IP" "$i")
    ports+=("$port")
    if [ $((i % 3)) -eq 0 ]; then
        echo -e "  Request $i -> Target server on port $port"
    fi
    sleep 0.3
done

# Check consistency
all_same=true
first_port="${ports[0]}"
for port in "${ports[@]}"; do
    if [ "$port" != "$first_port" ]; then
        all_same=false
        break
    fi
done

if [ "$all_same" = true ]; then
    echo -e "${GREEN}✓ PASS: Client $CLIENT2_IP consistently routed to port $first_port${NC}"
else
    echo -e "${RED}✗ FAIL: Client $CLIENT2_IP was routed to different targets${NC}"
    unique_ports_list=$(printf '%s\n' "${ports[@]}" | sort -u | tr '\n' ' ')
    echo -e "${RED}  Unique ports seen: $unique_ports_list${NC}"
fi
echo ""

# Test 4: Multiple clients maintain their own sticky sessions
echo -e "${GREEN}Test 4: Multiple clients maintain independent sticky sessions${NC}"
echo -e "${YELLOW}Making 3 requests from each of 3 different clients...${NC}"

client1_ports=()
client2_ports=()
client3_ports=()

for i in {1..3}; do
    client1_ports+=($(make_request "$CLIENT1_IP" "$i"))
    client2_ports+=($(make_request "$CLIENT2_IP" "$i"))
    client3_ports+=($(make_request "$CLIENT3_IP" "$i"))
    sleep 0.2
done

# Check each client's consistency
all_pass=true

# Client 1
c1_first="${client1_ports[0]}"
c1_consistent=true
for p in "${client1_ports[@]}"; do
    if [ "$p" != "$c1_first" ]; then
        c1_consistent=false
        break
    fi
done

# Client 2
c2_first="${client2_ports[0]}"
c2_consistent=true
for p in "${client2_ports[@]}"; do
    if [ "$p" != "$c2_first" ]; then
        c2_consistent=false
        break
    fi
done

# Client 3
c3_first="${client3_ports[0]}"
c3_consistent=true
for p in "${client3_ports[@]}"; do
    if [ "$p" != "$c3_first" ]; then
        c3_consistent=false
        break
    fi
done

if [ "$c1_consistent" = true ] && [ "$c2_consistent" = true ] && [ "$c3_consistent" = true ]; then
    echo -e "${GREEN}✓ PASS: All clients maintain their own sticky sessions${NC}"
    echo -e "  Client $CLIENT1_IP -> Port $c1_first (all 3 requests)"
    echo -e "  Client $CLIENT2_IP -> Port $c2_first (all 3 requests)"
    echo -e "  Client $CLIENT3_IP -> Port $c3_first (all 3 requests)"
else
    echo -e "${RED}✗ FAIL: Some clients did not maintain sticky sessions${NC}"
    [ "$c1_consistent" = false ] && echo -e "${RED}  Client $CLIENT1_IP inconsistent: ${client1_ports[*]}${NC}"
    [ "$c2_consistent" = false ] && echo -e "${RED}  Client $CLIENT2_IP inconsistent: ${client2_ports[*]}${NC}"
    [ "$c3_consistent" = false ] && echo -e "${RED}  Client $CLIENT3_IP inconsistent: ${client3_ports[*]}${NC}"
    all_pass=false
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
if [ "$all_pass" = true ] && [ "$all_same" = true ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi

