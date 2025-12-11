# Flask Load Balancer

A Python load balancer implementation using Flask that supports path-based routing, DNS resolution, and multiple load balancing algorithms.

## Features

- **Environment Variable Configuration**: Fully configurable via environment variables
- **DNS Resolution**: Resolves hostnames to multiple IP addresses
- **Multiple Load Balancing Algorithms**: Round Robin, Weighted, and Least Response Time (LRT)
- **Path-Based Routing**: Routes requests based on URI path prefixes
- **URI Rewriting**: Strips path prefixes before forwarding requests
- **Health Checks**: Optional periodic health checks with configurable thresholds to monitor target availability
- **Robust Error Handling**: Returns appropriate HTTP status codes (404, 502, 503, 504)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

The load balancer is configured entirely through environment variables.

### Required Environment Variables

#### Basic Configuration

- `LISTENER_PORT` (integer): Port that the load balancer listens on for incoming connections. Default: `8080`
- `CONNECTION_TIMEOUT` (integer): Timeout in milliseconds for upstream requests. Default: `5000`
- `LOAD_BALANCING_ALGORITHM` (string): Load balancing algorithm to use. Options:
  - `ROUND_ROBIN`: Evenly distributes requests in a circular pattern (implemented)
  - `WEIGHTED`: Weighted distribution based on target weights (implemented)
  - `STICKY`: Sticky sessions (not implemented - falls back to first target)
  - `LRT`: Least Response Time - selects target with lowest (active_connections × avg_ttfb) (implemented)
  Default: `ROUND_ROBIN`
- `HEADER_CONVENTION_ENABLE` (boolean): When `true`, the load balancer adds common proxy headers to upstream requests:
  - `X-Forwarded-For`: Client IP address (appended if already present)
  - `X-Forwarded-Host`: Original host header from client request
  - `X-Forwarded-Port`: Listener port
  - `X-Forwarded-Proto`: Request scheme (http/https)
  - `X-Real-IP`: Client IP address
  - `X-Request-Id`: Unique request identifier (UUID)
  Default: `false`

#### Target Groups

Target groups define sets of backend servers. Each target group is configured using numbered environment variables:

- `TARGET_GROUP_<N>_NAME` (string): Name of the target group
- `TARGET_GROUP_<N>_TARGETS` (string): Comma-delimited list of targets in the format `<hostname>:<port>/<base-uri>`

**Target Format:**
- `<hostname>`: Can be a hostname (resolved via DNS) or IP address
- `<port>`: Port number
- `<base-uri>`: Optional base URI path (defaults to `/`)

**Examples:**
- `127.0.0.1:8080` - Single IP with default base URI `/`
- `127.0.0.1:8080/api` - Single IP with base URI `/api`
- `example.com:80` - Hostname resolved via DNS
- `backend.example.com:8080/v1,backend2.example.com:8080/v1` - Multiple targets

**Note:** If a hostname resolves to multiple IP addresses, each IP address becomes a separate target.

#### Weighted Load Balancing

When using the `WEIGHTED` load balancing algorithm, you can configure weights for targets to control the distribution of traffic. Higher weights receive proportionally more requests.

**Weight Configuration:**

- `TARGET_GROUP_<N>_WEIGHTS` (string): Comma-delimited list of `<hostname>:<weight>` entries
  - Format: `hostname1:weight1,hostname2:weight2,...`
  - Weight must be an integer >= 1
  - All targets in the target group must have weights specified when using WEIGHTED algorithm

**Example:**
```bash
export LOAD_BALANCING_ALGORITHM=WEIGHTED
export TARGET_GROUP_1_NAME=backend
export TARGET_GROUP_1_TARGETS=server1.com:8080,server2.com:8080,server3.com:8080
export TARGET_GROUP_1_WEIGHTS=server1.com:1,server2.com:2,server3.com:5
```

In this example:
- `server1.com` receives 1/8 of requests (weight 1)
- `server2.com` receives 2/8 of requests (weight 2)
- `server3.com` receives 5/8 of requests (weight 5)

**Note:** When using WEIGHTED algorithm, all targets must have weights configured. If weights are missing, the configuration will raise an error.

#### Health Checks

Target groups can optionally be configured with periodic health checks to monitor the availability of targets. Health checks confirm whether a target is available by periodically sending HTTP requests. If health checks fail over a given threshold, the target is temporarily removed from the group until the health check succeeds over a given threshold.

**Health Check Configuration Parameters:**

- `TARGET_GROUP_<N>_HEALTH_CHECK_ENABLED` (boolean): Enables health checks for this target group. Options: `true` or `false`. Default: `false`
- `TARGET_GROUP_<N>_HEALTH_CHECK_PATH` (string): The HTTP path to request for health checks. Default: `/health`
- `TARGET_GROUP_<N>_HEALTH_CHECK_INTERVAL` (integer): Interval between health checks in milliseconds. Default: `30000` (30 seconds)
- `TARGET_GROUP_<N>_HEALTH_CHECK_SUCCEED_THRESHOLD` (integer): Number of consecutive successful health checks (HTTP 200) required to mark a target as healthy. Default: `2`
- `TARGET_GROUP_<N>_HEALTH_CHECK_FAILURE_THRESHOLD` (integer): Number of consecutive failed health checks required to mark a target as unhealthy. Default: `2`

**Default Values:**

| Parameter | Default Value |
|-----------|---------------|
| Health Check Enabled | `false` |
| Health Check Path | `/health` |
| Health Check Interval | `30000` ms (30 seconds) |
| Succeed Threshold | `2` |
| Failure Threshold | `2` |

**Health Check Behavior:**

- Health checks are performed in a background daemon thread for each target group
- A health check request is performed by sending an HTTP GET request to `http://<target_ip>:<target_port><health_check_path>`
- **Only HTTP 200 responses are considered successful**; any other status code (400, 401, 403, 404, 500, 502, 503, 504, etc.) or connection error is considered a failure
- Health check requests have a 5-second timeout
- Targets transition between healthy and unhealthy states only after reaching the configured thresholds:
  - A target must reach the `SUCCEED_THRESHOLD` consecutively before being marked **healthy**
  - A target must reach the `FAILURE_THRESHOLD` consecutively before being marked **unhealthy**
- When health checks are enabled, only healthy targets are used for load balancing
- If all targets become unhealthy, a 503 error is returned to clients
- Health checks don't affect targets if disabled

**How Health Checks Work:**

1. **Background Thread**: Each target group with health checks enabled gets its own background daemon thread
2. **Periodic Requests**: Every `HEALTH_CHECK_INTERVAL` milliseconds, the load balancer sends GET requests to `<target_ip>:<target_port><HEALTH_CHECK_PATH>`
3. **Success/Failure Detection**: HTTP 200 = success, anything else = failure
4. **State Changes**: 
   - After `SUCCEED_THRESHOLD` consecutive successes → target marked healthy
   - After `FAILURE_THRESHOLD` consecutive failures → target marked unhealthy
5. **Load Balancing**: Only healthy targets receive traffic

**Health Check Configuration Examples:**

**Example 1: Basic Health Checks (10 second interval)**
```bash
export TARGET_GROUP_1_NAME=api_backend
export TARGET_GROUP_1_TARGETS=api1.example.com:8080,api2.example.com:8080
export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=true
export TARGET_GROUP_1_HEALTH_CHECK_PATH=/health
export TARGET_GROUP_1_HEALTH_CHECK_INTERVAL=10000
export TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD=2
export TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD=2
```

**Example 2: Aggressive Health Checks (5 second interval, fast detection)**
```bash
export TARGET_GROUP_1_NAME=critical_backend
export TARGET_GROUP_1_TARGETS=critical1.example.com:8080,critical2.example.com:8080
export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=true
export TARGET_GROUP_1_HEALTH_CHECK_PATH=/healthz
export TARGET_GROUP_1_HEALTH_CHECK_INTERVAL=5000
export TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD=1
export TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD=1
```

**Example 3: Conservative Health Checks (60 second interval, stable detection)**
```bash
export TARGET_GROUP_1_NAME=stable_backend
export TARGET_GROUP_1_TARGETS=stable1.example.com:8080,stable2.example.com:8080
export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=true
export TARGET_GROUP_1_HEALTH_CHECK_PATH=/health
export TARGET_GROUP_1_HEALTH_CHECK_INTERVAL=60000
export TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD=3
export TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD=5
```

**Example 4: Complete Configuration with Health Checks**
```bash
export LISTENER_PORT=8080
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=ROUND_ROBIN

# Target Group with Health Checks
export TARGET_GROUP_1_NAME=backend
export TARGET_GROUP_1_TARGETS=backend1.example.com:8080,backend2.example.com:8080
export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=true
export TARGET_GROUP_1_HEALTH_CHECK_PATH=/health
export TARGET_GROUP_1_HEALTH_CHECK_INTERVAL=10000
export TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD=2
export TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD=3

# Listener Rule
export LISTENER_RULE_1_PATH_PREFIX=/
export LISTENER_RULE_1_PATH_REWRITE=
export LISTENER_RULE_1_TARGET_GROUP=backend
```

**Health Check Request Example:**

```
GET /health HTTP/1.1
Host: target.example.com:8080
Connection: close
Timeout: 5 seconds

Response: HTTP/1.1 200 OK
Result: SUCCESS ✓ (target marked healthy after threshold)
```

```
GET /health HTTP/1.1
Host: target.example.com:8080
Connection: close
Timeout: 5 seconds

Response: HTTP/1.1 503 Service Unavailable
Result: FAILURE ✗ (target marked unhealthy after threshold)
```

**Health Check Architecture:**

```
┌─────────────────────────────────────────────────────┐
│             Load Balancer Application               │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │        Target Group 1 (with HC)             │   │
│  │  ┌──────────────────────────────────────┐   │   │
│  │  │ Background Health Check Thread       │   │   │
│  │  │ • Checks targets every interval      │   │   │
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

**Troubleshooting Health Checks:**

**Health Checks Not Running?**
- Check that `TARGET_GROUP_<N>_HEALTH_CHECK_ENABLED=true`
- Ensure health check path is correct (default: `/health`)
- Check that mock targets implement the health endpoint
- Verify targets are running on configured ports

**All Targets Unhealthy?**
- Load balancer returns 503 error
- Check target health endpoint responds with HTTP 200
- Verify targets are running on configured ports
- Reduce `HEALTH_CHECK_FAILURE_THRESHOLD` for faster recovery
- Check network connectivity between load balancer and targets

**False Positives?**
- Adjust `FAILURE_THRESHOLD` higher for more stable detection
- Increase `HEALTH_CHECK_INTERVAL` to avoid temporary network blips
- Ensure health check path is correct and targets respond with 200

**Targets Not Recovering?**
- Check that targets are actually healthy (test health endpoint directly)
- Verify `SUCCEED_THRESHOLD` is not too high
- Ensure health check path is accessible

#### Listener Rules

Listener rules map incoming request paths to target groups. Each listener rule is configured using numbered environment variables:

- `LISTENER_RULE_<N>_PATH_PREFIX` (string): URI path prefix to match against incoming requests
- `LISTENER_RULE_<N>_PATH_REWRITE` (string): Optional prefix to strip from the URI before forwarding (defaults to empty string)
- `LISTENER_RULE_<N>_TARGET_GROUP` (string): Name of the target group to route matched requests to

**Note:** Listener rules are matched in order of path prefix length (longest first), so more specific paths should be configured first.

## Configuration Examples

### Example 1: Simple Single Backend

```bash
export LISTENER_PORT=8080
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=ROUND_ROBIN

# Target Group
export TARGET_GROUP_1_NAME=backend
export TARGET_GROUP_1_TARGETS=127.0.0.1:8080

# Listener Rule
export LISTENER_RULE_1_PATH_PREFIX=/
export LISTENER_RULE_1_PATH_REWRITE=
export LISTENER_RULE_1_TARGET_GROUP=backend
```

### Example 2: Multiple Backends with Path-Based Routing

```bash
export LISTENER_PORT=8080
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=ROUND_ROBIN

# Target Groups
export TARGET_GROUP_1_NAME=api_backend
export TARGET_GROUP_1_TARGETS=api1.example.com:8080,api2.example.com:8080

export TARGET_GROUP_2_NAME=web_backend
export TARGET_GROUP_2_TARGETS=web1.example.com:8080,web2.example.com:8080

# Listener Rules
export LISTENER_RULE_1_PATH_PREFIX=/api
export LISTENER_RULE_1_PATH_REWRITE=/api
export LISTENER_RULE_1_TARGET_GROUP=api_backend

export LISTENER_RULE_2_PATH_PREFIX=/web
export LISTENER_RULE_2_PATH_REWRITE=/web
export LISTENER_RULE_2_TARGET_GROUP=web_backend
```

### Example 3: URI Rewriting

```bash
export LISTENER_PORT=8080
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=ROUND_ROBIN

# Target Group
export TARGET_GROUP_1_NAME=backend
export TARGET_GROUP_1_TARGETS=127.0.0.1:8080/v1

# Listener Rule
# Requests to /my/listener/resource will be rewritten to /v1/resource
export LISTENER_RULE_1_PATH_PREFIX=/my/listener
export LISTENER_RULE_1_PATH_REWRITE=/my/listener
export LISTENER_RULE_1_TARGET_GROUP=backend
```

### Example 4: Weighted Load Balancing

```bash
export LISTENER_PORT=8080
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=WEIGHTED

# Target Group with Weights
export TARGET_GROUP_1_NAME=backend
export TARGET_GROUP_1_TARGETS=server1.com:8080,server2.com:8080,server3.com:8080
export TARGET_GROUP_1_WEIGHTS=server1.com:1,server2.com:2,server3.com:5

# Listener Rule
export LISTENER_RULE_1_PATH_PREFIX=/
export LISTENER_RULE_1_PATH_REWRITE=
export LISTENER_RULE_1_TARGET_GROUP=backend
```

In this example, traffic is distributed with a 1:2:5 ratio (server1 gets 1/8, server2 gets 2/8, server3 gets 5/8 of requests).

### Example 5: Least Response Time (LRT) Algorithm

```bash
export LISTENER_PORT=8080
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=LRT

# Target Group
export TARGET_GROUP_1_NAME=backend
export TARGET_GROUP_1_TARGETS=server1.com:8080,server2.com:8080,server3.com:8080

# Listener Rule
export LISTENER_RULE_1_PATH_PREFIX=/
export LISTENER_RULE_1_PATH_REWRITE=
export LISTENER_RULE_1_TARGET_GROUP=backend
```

The LRT algorithm selects the target with the lowest metric: `active_connections × average_time_to_first_byte`.

## Running the Load Balancer

```bash
python app.py
```

Or using Flask directly:

```bash
flask run --host=0.0.0.0 --port=8080
```

## How It Works

1. **Request Reception**: The load balancer receives HTTP requests on the configured listener port.

2. **Path Matching**: The load balancer matches the request path against configured listener rules (longest prefix first).

3. **Target Selection**: If a matching rule is found, the load balancer selects a target from the associated target group using the configured algorithm (Round Robin by default).

4. **URI Rewriting**: The request path is rewritten according to the listener rule configuration.

5. **Request Forwarding**: The request is forwarded to the selected target with appropriate headers and body.

6. **Response**: The response from the target is returned to the client with the original status code and headers.

## Error Handling

The load balancer returns appropriate HTTP status codes:

- **404**: No listener rule matched the request path
- **502**: Connection error occurred while forwarding the request
- **503**: No targets available in the target group
- **504**: Request timeout exceeded

All error responses have empty payloads as per requirements.

## DNS Resolution

The load balancer automatically resolves hostnames to IP addresses. If a hostname resolves to multiple IP addresses, each IP address becomes a separate target in the target group, enabling automatic load distribution across multiple servers behind a single hostname.

## Testing

### Mock Target Servers

A mock target server (`mock_target.py`) is provided for testing purposes. It simulates downstream targets and returns JSON responses with request information.

#### Running Mock Targets

**Single mock target:**
```bash
python mock_target.py 8081
```

**Multiple mock targets (in separate terminals):**
```bash
# Terminal 1
python mock_target.py 8081

# Terminal 2
python mock_target.py 8082

# Terminal 3
python mock_target.py 8083
```

**With optional configuration:**
```bash
# Add delay (in milliseconds)
MOCK_DELAY_MS=100 python mock_target.py 8081

# Return error code
MOCK_ERROR_CODE=500 python mock_target.py 8081
```

#### Testing Health Checks

**1. Pytest Test Suite**

Run the comprehensive pytest test suite for health checks:

```bash
pytest tests/test_health_checks.py -v
```

This test suite covers:
- Health check configuration parameters
- Periodic health check execution
- Target removal when health checks fail over threshold
- Target re-addition when health checks succeed over threshold
- Non-200 response codes are considered failures
- Only healthy targets receive traffic
- Integration tests with real HTTP servers

**2. Integration Test**

Run the integration test script that starts mock targets and the load balancer:

```bash
python tests/test_integration.py
```

This script:
- Starts mock target servers
- Configures a load balancer with health checks enabled
- Makes test requests to verify functionality
- Automatically cleans up when complete

**3. Manual Health Check Testing**

**Step 1: Start mock targets that respond to health checks:**
```bash
# Terminal 1
python mock_target.py 8081

# Terminal 2  
python mock_target.py 8082

# Terminal 3
python mock_target.py 8083
```

**Step 2: Configure environment variables with health checks enabled:**
```bash
export LISTENER_PORT=8080
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=ROUND_ROBIN

export TARGET_GROUP_1_NAME=backends
export TARGET_GROUP_1_TARGETS=127.0.0.1:8081,127.0.0.1:8082,127.0.0.1:8083
export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=true
export TARGET_GROUP_1_HEALTH_CHECK_PATH=/health
export TARGET_GROUP_1_HEALTH_CHECK_INTERVAL=5000
export TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD=1
export TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD=1

export LISTENER_RULE_1_PATH_PREFIX=/
export LISTENER_RULE_1_PATH_REWRITE=
export LISTENER_RULE_1_TARGET_GROUP=backends
```

**Step 3: Start the load balancer:**
```bash
# Terminal 4
python app.py
```

**Step 4: Make requests to test:**
```bash
# Make multiple requests
for i in {1..10}; do
    echo "Request $i:"
    curl -s http://localhost:8080/api/test | python -m json.tool | head -5
    echo ""
    sleep 1
done
```

**Step 5: Test unhealthy target removal:**
```bash
# Stop one mock target (Ctrl+C in its terminal)
# Wait for health check interval + failure threshold
# Make requests - should only go to remaining healthy targets
curl http://localhost:8080/api/test
```

**Step 6: Test target recovery:**
```bash
# Restart the stopped mock target
python mock_target.py 8081

# Wait for health check interval + succeed threshold
# Make requests - should now include the recovered target
curl http://localhost:8080/api/test
```

#### Quick Test Setup (container)

Run the load balancer in a container (in a separate terminal) using Podman Compose:

```bash
podman compose -f podman-compose.yml up --build
```

Start three mock downstream targets for the containerized load balancer:

```bash
chmod +x mock_downstream_targets_container.sh
./mock_downstream_targets_container.sh
```

The script launches mock targets on ports 8081, 8082, and 8083 and keeps them running until you stop it (Ctrl+C).

#### Running Test Examples

Once the load balancer and mock targets are running, use the test examples script:

```bash
chmod +x tests/test_examples.sh
./tests/test_examples.sh
```

Or test manually:
```bash
# Test round-robin distribution
for i in {1..6}; do
    curl http://localhost:8080/test
done

# Test different paths
curl http://localhost:8080/api/users
curl http://localhost:8080/web/dashboard
```

#### Manual Testing Setup

1. **Start mock targets:**
```bash
python mock_target.py 8081 &
python mock_target.py 8082 &
python mock_target.py 8083 &
```

2. **Configure and start load balancer:**
```bash
export LISTENER_PORT=8080
export CONNECTION_TIMEOUT=5000
export LOAD_BALANCING_ALGORITHM=ROUND_ROBIN
export TARGET_GROUP_1_NAME=backend
export TARGET_GROUP_1_TARGETS=127.0.0.1:8081,127.0.0.1:8082,127.0.0.1:8083
export LISTENER_RULE_1_PATH_PREFIX=/
export LISTENER_RULE_1_PATH_REWRITE=
export LISTENER_RULE_1_TARGET_GROUP=backend

python app.py
```

3. **Test the load balancer:**
```bash
curl http://localhost:8080/test
```

The mock target will return JSON showing which server handled the request, allowing you to verify round-robin distribution.

#### Testing Error Scenarios

**Test 503 (No targets available):**
- Stop all mock target servers
- Make a request to the load balancer

**Test 504 (Timeout):**
- Start a mock target with high delay: `MOCK_DELAY_MS=10000 python mock_target.py 8081`
- Set low timeout: `export CONNECTION_TIMEOUT=1000`
- Make a request

**Test 404 (No matching rule):**
- Make a request to a path that doesn't match any listener rule

**Test 502 (Connection error):**
- Configure a target with invalid host/port
- Make a request

## Health Check Implementation Details

### Health Check Flow

1. **Initialization** (app.py)
   - `start_health_checks()` is called during app startup
   - Creates `HealthCheck` instance for each enabled target group
   - Health check threads are started as daemon threads

2. **Background Execution** (health_check.py)
   - `HealthCheck` runs in a daemon thread per target group
   - Every `interval_ms`, checks each target in the group
   - Tracks consecutive successes/failures per target
   - Health check requests use a 5-second timeout

3. **State Management** (health_check.py)
   - Each target tracks: `consecutive_failures`, `consecutive_successes`, `healthy` status
   - Transitions to healthy when `consecutive_successes >= succeed_threshold`
   - Transitions to unhealthy when `consecutive_failures >= failure_threshold`
   - State changes are atomic operations

4. **Load Balancing** (load_balancer.py)
   - `select_target()` calls `target_group.get_healthy_targets()`
   - Only healthy targets are candidates for selection
   - If no healthy targets exist, 503 error is returned
   - All load balancing algorithms (Round Robin, Weighted, LRT) work with filtered healthy targets

5. **Shutdown** (app.py)
   - `stop_health_checks()` stops all health check threads gracefully
   - Called via `atexit` handler on application shutdown
   - Threads are joined with a timeout to prevent hanging

### Thread Safety

- Health checks run in daemon threads (one per target group)
- Target health state is updated atomically
- Load balancer reads health state atomically
- Python GIL protects dictionary operations for thread safety
- No explicit locks needed for basic operations

### Performance Considerations

- Background threads are low-priority daemon threads
- Configurable health check intervals (minimum recommended: 5 seconds)
- Network timeouts set to 5 seconds to prevent hanging
- Health check failures don't block request processing
- Health checks are performed asynchronously and don't impact request latency

### Files Related to Health Checks

- `health_check.py` - Core health check implementation
- `target_group.py` - Health check configuration and filtering
- `config.py` - Health check environment variable parsing
- `load_balancer.py` - Integration with target selection
- `app.py` - Health check lifecycle management
- `tests/test_health_checks.py` - Comprehensive pytest test suite
- `tests/test_integration.py` - Integration test script

## Test Suites

The project includes comprehensive test suites:

- **`tests/test_error_handling.py`**: Tests error handling (404, 502, 503, 504) and upstream error propagation
- **`tests/test_weighted_load_balancing.py`**: Tests weighted load balancing algorithm and weight configuration
- **`tests/test_health_checks.py`**: Tests health check functionality, thresholds, and target filtering
- **`tests/test_integration.py`**: Integration tests that start mock targets and verify end-to-end functionality
- **`tests/soak_test.py`**: Soak/load testing script for performance evaluation

Run all tests:
```bash
pytest tests/ -v
```

Run specific test suite:
```bash
pytest tests/test_health_checks.py -v
pytest tests/test_weighted_load_balancing.py -v
pytest tests/test_error_handling.py -v
```

## Build and Deployment

### Docker/Podman

The project includes a `Dockerfile` and `podman-compose.yml` for containerized deployment:

```bash
# Build and run with Podman Compose
podman compose -f podman-compose.yml up --build

# Or build manually
docker build -t load-balancer .
docker run -p 8080:8080 load-balancer
```

The container runs with Gunicorn using 4 workers and threads for production use.

### Build Scripts

- `arm64-build.sh`: Build script for ARM64 architecture
- `x86_64-build.sh`: Build script for x86_64 architecture

## Notes

- The load balancer only handles HTTP requests (not HTTPS)
- Hop-by-hop headers (Host, Connection, Keep-Alive, Transfer-Encoding) are automatically excluded from forwarded requests
- Query strings are preserved when forwarding requests
- **Implemented algorithms**: Round Robin, Weighted, and Least Response Time (LRT)
- **STICKY algorithm**: Not implemented - falls back to selecting the first target
- When using WEIGHTED algorithm, all targets must have weights configured via `TARGET_GROUP_<N>_WEIGHTS`
- Health checks run in background daemon threads and don't block request processing

