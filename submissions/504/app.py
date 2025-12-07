"""
Flask Load Balancer Application
Main entry point for the load balancer service.
"""
from flask import Flask, request, Response
import os
from config import Config
from load_balancer import LoadBalancer
from error_handler import handle_error

app = Flask(__name__)

# Initialize configuration
config = Config()
load_balancer = LoadBalancer(config)


@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
def proxy(path):
    """
    Main proxy endpoint that handles all incoming requests.
    """
    try:
        # Reconstruct the full path
        full_path = f'/{path}' if path else '/'
        
        # Find matching listener rule
        listener_rule = config.find_listener_rule(full_path)
        
        if not listener_rule:
            return handle_error(404, "No listener rule matched")
        
        # Get target group
        target_group = config.get_target_group(listener_rule.target_group)
        
        if not target_group:
            return handle_error(503, "Target group not found")
        
        # Get targets from target group
        targets = target_group.get_targets()
        
        if not targets:
            return handle_error(503, "No targets available")
        
        # Select target using load balancing algorithm
        target = load_balancer.select_target(target_group, request)
        
        if not target:
            return handle_error(503, "No target available")
        
        # Rewrite URI if needed
        rewritten_path = listener_rule.rewrite_uri(full_path)
        
        # Forward request to target
        response = load_balancer.forward_request(
            target,
            request,
            rewritten_path
        )
        
        return response
        
    except Exception as e:
        # Handle connection errors
        return handle_error(502, f"Connection error: {str(e)}")


if __name__ == '__main__':
    port = config.get_listener_port()
    app.run(host='0.0.0.0', port=port, debug=False)