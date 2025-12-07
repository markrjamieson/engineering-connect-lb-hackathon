# Flask Load Balancer

A Python load balancer implementation using Flask that supports path-based routing, DNS resolution, and multiple load balancing algorithms.

## Features

- **Environment Variable Configuration**: Fully configurable via environment variables
- **DNS Resolution**: Resolves hostnames to multiple IP addresses
- **Round Robin Load Balancing**: Evenly distributes requests across targets
- **Path-Based Routing**: Routes requests based on URI path prefixes
- **URI Rewriting**: Strips path prefixes before forwarding requests
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
  - `WEIGHTED`: Weighted distribution (not implemented)
  - `STICKY`: Sticky sessions (not implemented)
  - `LRT`: Least Response Time (not implemented)
  Default: `ROUND_ROBIN`

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

#### Quick Test Setup

Use the provided test script to start multiple mock targets and the load balancer:

```bash
chmod +x test_load_balancer.sh
./test_load_balancer.sh
```

This script:
- Starts 3 mock target servers on ports 8081, 8082, and 8083
- Configures the load balancer to route to all 3 targets
- Starts the load balancer on port 8080
- Automatically cleans up when stopped (Ctrl+C)

#### Running Test Examples

Once the load balancer and mock targets are running, use the test examples script:

```bash
chmod +x test_examples.sh
./test_examples.sh
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

## Notes

- The load balancer only handles HTTP requests (not HTTPS)
- Hop-by-hop headers (Host, Connection, Keep-Alive, Transfer-Encoding) are automatically excluded from forwarded requests
- Query strings are preserved when forwarding requests
- Currently only Round Robin algorithm is fully implemented; other algorithms default to Round Robin behavior

