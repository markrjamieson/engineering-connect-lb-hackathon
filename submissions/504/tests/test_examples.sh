#!/bin/bash

# Example test commands for the load balancer
# Make sure the load balancer and mock targets are running first

LB_URL="http://localhost:8080"

echo "Testing Load Balancer"
echo "===================="
echo ""

echo "1. Testing basic request (should round-robin across 3 targets):"
for i in {1..6}; do
    echo "Request $i:"
    curl -s "$LB_URL/test" | python -m json.tool | grep server_port
done

echo ""
echo "2. Testing path-based routing:"
curl -s "$LB_URL/api/users" | python -m json.tool

echo ""
echo "3. Testing POST request:"
curl -s -X POST "$LB_URL/data" -H "Content-Type: application/json" -d '{"test": "data"}' | python -m json.tool

echo ""
echo "4. Testing 404 (no matching rule):"
curl -i "$LB_URL/nonexistent/path" 2>/dev/null | head -1

echo ""
echo "5. Testing with query parameters:"
curl -s "$LB_URL/search?q=test&page=1" | python -m json.tool

