#!/bin/bash
# Quick script to verify health checks are disabled

echo "============================================================"
echo "Checking Health Check Configuration"
echo "============================================================"
echo ""

# Check environment variables
echo "1. Environment Variables:"
echo "------------------------"
if env | grep -q "TARGET_GROUP.*HEALTH_CHECK_ENABLED"; then
    env | grep "TARGET_GROUP.*HEALTH_CHECK_ENABLED" | while read line; do
        echo "  $line"
        if echo "$line" | grep -qi "=true"; then
            echo "    ⚠️  WARNING: Health checks are ENABLED"
        elif echo "$line" | grep -qi "=false"; then
            echo "    ✓ Health checks are DISABLED"
        fi
    done
else
    echo "  No HEALTH_CHECK_ENABLED variables found"
    echo "  (This means health checks default to DISABLED)"
fi

echo ""
echo "2. Running Processes:"
echo "---------------------"
if pgrep -f "app.py|gunicorn" > /dev/null; then
    echo "  ✓ Load balancer process is running"
    echo ""
    echo "  Process details:"
    ps aux | grep -E "(app\.py|gunicorn)" | grep -v grep | head -1
    echo ""
    echo "  ⚠️  IMPORTANT: If you changed environment variables,"
    echo "     you MUST restart the application for changes to take effect!"
else
    echo "  No load balancer process found"
fi

echo ""
echo "3. To Disable Health Checks:"
echo "----------------------------"
echo "  1. Set environment variable:"
echo "     export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=false"
echo ""
echo "  2. Restart the application completely"
echo ""
echo "  3. Verify with:"
echo "     python check_health_check_status.py --env-only"

