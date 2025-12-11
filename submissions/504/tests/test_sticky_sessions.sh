#!/bin/bash

# Test script for sticky session load balancing
# This demonstrates that clients are assigned to the same target until TTL expires

LB_URL="http://localhost:8080"

# Determine Python command (python3 or python)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python."
    exit 1
fi

# Check if load balancer is running
if ! curl -s "$LB_URL" > /dev/null 2>&1; then
    echo "Error: Load balancer is not running on $LB_URL"
    echo "Please start it first with: ./setup_sticky_sessions.sh"
    exit 1
fi

echo "=========================================="
echo "Testing Sticky Session Load Balancing"
echo "=========================================="
echo ""
echo "This test verifies that:"
echo "  - Same client IP gets the same target (sticky)"
echo "  - After TTL expires, a new session is created using round-robin"
echo "  - The new session sticks to the new target until TTL expires again"
echo "  - Different client IPs can get different targets"
echo ""

# Function to extract server port from JSON response
get_server_port() {
    curl -s "$1" | $PYTHON_CMD -c "import sys, json; print(json.load(sys.stdin).get('server_port', 'unknown'))" 2>/dev/null
}

# Test 1: Same client should get the same target
echo "1. Testing sticky behavior (same client IP):"
echo "   Making 5 requests from the same client..."
echo "   (All requests should go to the same server)"
PORTS=()
for i in {1..5}; do
    PORT=$(get_server_port "$LB_URL/test")
    PORTS+=($PORT)
    echo "   Request $i: server_port=$PORT"
done

# Check if all ports are the same
UNIQUE_PORTS=($(printf '%s\n' "${PORTS[@]}" | sort -u))
if [ ${#UNIQUE_PORTS[@]} -eq 1 ]; then
    echo -e "   \033[0;32m✓ PASS: All requests went to the same server (port ${UNIQUE_PORTS[0]})\033[0m"
else
    echo -e "   \033[0;31m✗ FAIL: Requests went to different servers: ${PORTS[*]}\033[0m"
fi

echo ""

# Test 2: Different client IPs can get different targets
echo "2. Testing different client IPs:"
echo "   Making requests with different X-Forwarded-For headers..."
PORT1=$(curl -s -H "X-Forwarded-For: 192.168.1.100" "$LB_URL/test" | $PYTHON_CMD -c "import sys, json; print(json.load(sys.stdin).get('server_port', 'unknown'))" 2>/dev/null)
PORT2=$(curl -s -H "X-Forwarded-For: 192.168.1.101" "$LB_URL/test" | $PYTHON_CMD -c "import sys, json; print(json.load(sys.stdin).get('server_port', 'unknown'))" 2>/dev/null)
PORT3=$(curl -s -H "X-Forwarded-For: 192.168.1.102" "$LB_URL/test" | $PYTHON_CMD -c "import sys, json; print(json.load(sys.stdin).get('server_port', 'unknown'))" 2>/dev/null)

echo "   Client 192.168.1.100: server_port=$PORT1"
echo "   Client 192.168.1.101: server_port=$PORT2"
echo "   Client 192.168.1.102: server_port=$PORT3"

# Verify each client gets the same target on subsequent requests
PORT1_2=$(curl -s -H "X-Forwarded-For: 192.168.1.100" "$LB_URL/test" | $PYTHON_CMD -c "import sys, json; print(json.load(sys.stdin).get('server_port', 'unknown'))" 2>/dev/null)
if [ "$PORT1" == "$PORT1_2" ]; then
    echo -e "   \033[0;32m✓ PASS: Client 192.168.1.100 consistently gets port $PORT1\033[0m"
else
    echo -e "   \033[0;31m✗ FAIL: Client 192.168.1.100 got different ports ($PORT1 vs $PORT1_2)\033[0m"
fi

echo ""

# Test 3: Session expiration (wait for TTL to expire)
echo "3. Testing session expiration:"
echo "   Session TTL is 10 seconds (10000ms)"
echo "   Making initial request, then waiting 11 seconds..."
INITIAL_PORT=$(get_server_port "$LB_URL/test")
echo "   Initial request: server_port=$INITIAL_PORT"
echo "   Waiting 11 seconds for session to expire..."
sleep 11

# Make another request - should get a different target (round-robin)
AFTER_EXPIRY_PORT=$(get_server_port "$LB_URL/test")
echo "   After expiry: server_port=$AFTER_EXPIRY_PORT"

if [ "$INITIAL_PORT" != "$AFTER_EXPIRY_PORT" ]; then
    echo -e "   \033[0;32m✓ PASS: New target selected after session expiry\033[0m"
else
    echo -e "   \033[0;33m⚠ WARNING: Same target selected (may be round-robin cycle)\033[0m"
    echo "   Making a few more requests to verify round-robin..."
    for i in {1..3}; do
        PORT=$(get_server_port "$LB_URL/test")
        echo "   Request $i: server_port=$PORT"
    done
fi

echo ""

# Test 4: Multiple requests from same client within TTL
echo "4. Testing multiple requests within TTL:"
echo "   Making 10 rapid requests from same client..."
RAPID_PORTS=()
for i in {1..10}; do
    PORT=$(get_server_port "$LB_URL/test")
    RAPID_PORTS+=($PORT)
done

UNIQUE_RAPID=($(printf '%s\n' "${RAPID_PORTS[@]}" | sort -u))
if [ ${#UNIQUE_RAPID[@]} -eq 1 ]; then
    echo -e "   \033[0;32m✓ PASS: All 10 requests went to the same server (port ${UNIQUE_RAPID[0]})\033[0m"
else
    echo -e "   \033[0;31m✗ FAIL: Requests went to different servers: ${RAPID_PORTS[*]}\033[0m"
fi

echo ""

# Test 5: Verify new session sticks after expiration
echo "5. Testing new session after expiry (should stick to new target):"
echo "   Waiting for session to expire, then making 6 requests..."
sleep 11  # Wait for TTL to expire

echo "   Making 6 requests (should all go to the same new target):"
NEW_SESSION_PORTS=()
for i in {1..6}; do
    PORT=$(get_server_port "$LB_URL/test")
    NEW_SESSION_PORTS+=($PORT)
    echo "   Request $i: server_port=$PORT"
done

# Check if all ports are the same (new session should stick)
UNIQUE_NEW_SESSION=($(printf '%s\n' "${NEW_SESSION_PORTS[@]}" | sort -u))
if [ ${#UNIQUE_NEW_SESSION[@]} -eq 1 ]; then
    echo -e "   \033[0;32m✓ PASS: New session created and all requests stick to same target (port ${UNIQUE_NEW_SESSION[0]})\033[0m"
else
    echo -e "   \033[0;31m✗ FAIL: New session not sticking - requests went to different servers: ${NEW_SESSION_PORTS[*]}\033[0m"
fi

echo ""
echo "=========================================="
echo "Sticky Session Test Complete"
echo "=========================================="

