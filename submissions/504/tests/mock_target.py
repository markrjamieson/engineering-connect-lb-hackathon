"""
Mock Target Server
A simple HTTP server that can be used to simulate downstream targets for testing.
"""
from flask import Flask, request, jsonify
import sys
import time
import os

app = Flask(__name__)

# Get port from command line argument or environment variable
port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv('MOCK_PORT', '8080'))
delay_ms = int(os.getenv('MOCK_DELAY_MS', '0'))
error_code = int(os.getenv('MOCK_ERROR_CODE', '0')) if os.getenv('MOCK_ERROR_CODE') else None

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
def handle_request(path):
    """
    Handle all incoming requests and return a response with server identification.
    """
    # Simulate delay if configured
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
    
    # Return error if configured
    if error_code:
        return '', error_code
    
    # Reconstruct full path
    full_path = f'/{path}' if path else '/'
    
    # Build response data
    response_data = {
        'server_port': port,
        'method': request.method,
        'path': full_path,
        'query_string': request.query_string.decode('utf-8'),
        'headers': dict(request.headers),
        'body': request.get_data(as_text=True) if request.is_json or request.content_type == 'application/json' else None
    }
    
    return jsonify(response_data), 200


if __name__ == '__main__':
    print(f"Starting mock target server on port {port}")
    if delay_ms > 0:
        print(f"  Delay: {delay_ms}ms")
    if error_code:
        print(f"  Error code: {error_code}")
    app.run(host='0.0.0.0', port=port, debug=False)

