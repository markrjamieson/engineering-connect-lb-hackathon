#!/bin/bash

# Test script for path-based routing
# This demonstrates that different URI paths route to different target groups

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
    echo "Please start it first with: ./setup_path_based_routing.sh"
    exit 1
fi

echo "=========================================="
echo "Testing Path-Based Routing"
echo "=========================================="
echo ""
echo "This test verifies that:"
echo "  - /api/* requests → api_backend target group"
echo "  - /web/* requests → web_backend target group"
echo "  - /static/* requests → static_backend target group"
echo ""

# Test 1: API requests should always go to api_backend (ports 8081, 8082)
echo "1. Testing /api/* routes to api_backend:"
echo "   (Should show server_port: 8081 or 8082)"
for i in {1..5}; do
    echo "   Request $i to /api/users:"
    curl -s "$LB_URL/api/users" | $PYTHON_CMD -m json.tool 2>/dev/null | grep -E "(server_port|path)" | head -2 || echo "     Error: Failed to get response"
done

echo ""
echo "2. Testing /web/* routes to web_backend:"
echo "   (Should show server_port: 8083 or 8084)"
for i in {1..5}; do
    echo "   Request $i to /web/dashboard:"
    curl -s "$LB_URL/web/dashboard" | $PYTHON_CMD -m json.tool 2>/dev/null | grep -E "(server_port|path)" | head -2 || echo "     Error: Failed to get response"
done

echo ""
echo "3. Testing /static/* routes to static_backend:"
echo "   (Should show server_port: 8085)"
for i in {1..5}; do
    echo "   Request $i to /static/css/style.css:"
    curl -s "$LB_URL/static/css/style.css" | $PYTHON_CMD -m json.tool 2>/dev/null | grep -E "(server_port|path)" | head -2 || echo "     Error: Failed to get response"
done

echo ""
echo "4. Testing URI rewriting:"
echo "   Request to /api/v1/users should be rewritten (path_rewrite=/api):"
curl -s "$LB_URL/api/v1/users" | $PYTHON_CMD -m json.tool 2>/dev/null | grep -E "(server_port|path)" | head -2 || echo "     Error: Failed to get response"

echo ""
echo "5. Testing 404 for unmatched path:"
echo "   Request to /unknown/path (should return 404):"
curl -i "$LB_URL/unknown/path" 2>/dev/null | head -1

echo ""
echo "=========================================="
echo "Path-Based Routing Test Complete"
echo "=========================================="

