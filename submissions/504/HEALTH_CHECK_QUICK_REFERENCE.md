# Health Check Feature - Quick Reference Guide

## Configuration Environment Variables

### Basic Health Check Setup
```bash
# Enable health checks for target group 1
export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=true

# Set the health check endpoint path
export TARGET_GROUP_1_HEALTH_CHECK_PATH=/health

# Set how often to check (in milliseconds)
export TARGET_GROUP_1_HEALTH_CHECK_INTERVAL=30000

# How many successful checks before marking healthy
export TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD=2

# How many failed checks before marking unhealthy
export TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD=2
```

## Default Values

| Parameter | Default Value |
|-----------|---------------|
| Health Check Enabled | false |
| Health Check Path | /health |
| Health Check Interval | 30000 ms (30 seconds) |
| Succeed Threshold | 2 |
| Failure Threshold | 2 |

## Quick Examples

### Example 1: Basic Health Checks (10 second interval)
```bash
export TARGET_GROUP_1_NAME=api_backend
export TARGET_GROUP_1_TARGETS=api1.example.com:8080,api2.example.com:8080
export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=true
export TARGET_GROUP_1_HEALTH_CHECK_PATH=/health
export TARGET_GROUP_1_HEALTH_CHECK_INTERVAL=10000
```

### Example 2: Aggressive Health Checks (5 second interval)
```bash
export TARGET_GROUP_1_NAME=critical_backend
export TARGET_GROUP_1_TARGETS=critical1.example.com:8080,critical2.example.com:8080
export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=true
export TARGET_GROUP_1_HEALTH_CHECK_PATH=/healthz
export TARGET_GROUP_1_HEALTH_CHECK_INTERVAL=5000
export TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD=1
export TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD=1
```

### Example 3: Conservative Health Checks (60 second interval)
```bash
export TARGET_GROUP_1_NAME=stable_backend
export TARGET_GROUP_1_TARGETS=stable1.example.com:8080,stable2.example.com:8080
export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=true
export TARGET_GROUP_1_HEALTH_CHECK_PATH=/health
export TARGET_GROUP_1_HEALTH_CHECK_INTERVAL=60000
export TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD=3
export TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD=5
```

## Testing

### 1. Verify Implementation
```bash
python verify_health_checks.py
```

### 2. Run Interactive Demo
```bash
./test_health_checks.sh
```

### 3. Manual Test
```bash
# Terminal 1: Start mock target with health endpoint
python mock_target.py 8081

# Terminal 2: Configure and start load balancer
export TARGET_GROUP_1_NAME=test
export TARGET_GROUP_1_TARGETS=127.0.0.1:8081
export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=true
export LISTENER_RULE_1_PATH_PREFIX=/
export LISTENER_RULE_1_TARGET_GROUP=test
python app.py

# Terminal 3: Make requests
curl http://localhost:8080/api/test
```

## How Health Checks Work

1. **Background Thread**: Each target group with health checks enabled gets its own background thread
2. **Periodic Requests**: Every `HEALTH_CHECK_INTERVAL`, the load balancer sends GET requests to `<target_ip>:<target_port><HEALTH_CHECK_PATH>`
3. **Success/Failure**: HTTP 200 = success, anything else = failure
4. **State Changes**: 
   - After `SUCCEED_THRESHOLD` consecutive successes → target marked healthy
   - After `FAILURE_THRESHOLD` consecutive failures → target marked unhealthy
5. **Load Balancing**: Only healthy targets receive traffic

## Troubleshooting

### Health Checks Not Running?
- Check that `TARGET_GROUP_<N>_HEALTH_CHECK_ENABLED=true`
- Ensure health check path is correct (default: `/health`)
- Check that mock targets implement the health endpoint

### All Targets Unhealthy?
- Load balancer returns 503 error
- Check target health endpoint responds with HTTP 200
- Verify targets are running on configured ports
- Reduce `HEALTH_CHECK_FAILURE_THRESHOLD` for faster recovery

### False Positives?
- Adjust `FAILURE_THRESHOLD` higher for more stable detection
- Increase `HEALTH_CHECK_INTERVAL` to avoid temporary network blips

## Architecture

```
┌─────────────────────────────────────────────────────┐
│             Load Balancer Application               │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │        Target Group 1 (with HC)             │   │
│  │  ┌──────────────────────────────────────┐   │   │
│  │  │ Background Health Check Thread       │   │   │
│  │  │ • Checks targets every 10s           │   │   │
│  │  │ • Tracks healthy/unhealthy targets   │   │   │
│  │  │ • Filters for load balancer          │   │   │
│  │  └──────────────────────────────────────┘   │   │
│  │                                              │   │
│  │  Targets:                                    │   │
│  │  • 192.168.1.10:8080 [HEALTHY]              │   │
│  │  • 192.168.1.11:8080 [HEALTHY]              │   │
│  │  • 192.168.1.12:8080 [UNHEALTHY] ← filtered │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │      Load Balancer Selection Algorithm      │   │
│  │  • Selects from healthy targets only        │   │
│  │  • Uses round-robin or other algorithm      │   │
│  │  • Falls back to 503 if no healthy targets  │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Health Check Request Example

```
GET /health HTTP/1.1
Host: target.example.com:8080
Connection: close
Timeout: 5 seconds

Response: HTTP/1.1 200 OK
Result: SUCCESS ✓
```

```
GET /health HTTP/1.1
Host: target.example.com:8080
Connection: close
Timeout: 5 seconds

Response: HTTP/1.1 503 Service Unavailable
Result: FAILURE ✗
```

## Files Related to Health Checks

- `health_check.py` - Core health check implementation
- `HEALTH_CHECK_IMPLEMENTATION.md` - Detailed documentation
- `verify_health_checks.py` - Verification tests
- `test_health_checks.sh` - Interactive demo
- `README.md` - Updated with health check documentation

## Support and Documentation

- See `README.md` for full documentation
- See `HEALTH_CHECK_IMPLEMENTATION.md` for implementation details
- Run `python verify_health_checks.py` to verify feature works
- Run `./test_health_checks.sh` for interactive demo
