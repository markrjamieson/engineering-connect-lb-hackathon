"""
Load Balancer module.
Handles request forwarding and load balancing algorithms.
"""
import requests
from flask import Request, Response
from typing import Optional
from config import Config
from target_group import TargetGroup
from target import Target
from error_handler import handle_error


class LoadBalancer:
    """Handles load balancing and request forwarding."""
    
    def __init__(self, config: Config):
        """
        Initialize the load balancer.
        
        Args:
            config: The configuration object
        """
        self.config = config
        self.round_robin_counters = {}  # Track round robin state per target group
    
    def select_target(self, target_group: TargetGroup, request: Request) -> Optional[Target]:
        """
        Select a target from the target group using the configured algorithm.
        
        Args:
            target_group: The target group to select from
            request: The incoming request (for sticky sessions, etc.)
            
        Returns:
            Selected target or None if no targets available
        """
        targets = target_group.get_targets()
        
        if not targets:
            return None
        
        algorithm = self.config.get_load_balancing_algorithm()
        
        if algorithm == 'ROUND_ROBIN':
            return self._round_robin(target_group, targets)
        elif algorithm == 'WEIGHTED':
            # Not implemented yet
            return targets[0] if targets else None
        elif algorithm == 'STICKY':
            # Not implemented yet
            return targets[0] if targets else None
        elif algorithm == 'LRT':
            # Not implemented yet
            return targets[0] if targets else None
        else:
            # Default to round robin
            return self._round_robin(target_group, targets)
    
    def _round_robin(self, target_group: TargetGroup, targets: list) -> Target:
        """
        Select the next target using round robin algorithm.
        
        Args:
            target_group: The target group
            targets: List of available targets
            
        Returns:
            Selected target
        """
        group_name = target_group.name
        
        # Initialize counter if not exists
        if group_name not in self.round_robin_counters:
            self.round_robin_counters[group_name] = 0
        
        # Get current index
        index = self.round_robin_counters[group_name]
        
        # Select target
        target = targets[index % len(targets)]
        
        # Increment counter for next request
        self.round_robin_counters[group_name] = (index + 1) % len(targets)
        
        return target
    
    def forward_request(self, target: Target, request: Request, path: str) -> Response:
        """
        Forward a request to the target.
        
        Args:
            target: The target to forward to
            request: The incoming Flask request
            path: The rewritten path
            
        Returns:
            Response from the target or error response
        """
        try:
            # Construct full URL
            url = target.get_url(path)
            
            # Prepare request headers (exclude hop-by-hop headers)
            headers = {}
            for key, value in request.headers:
                if key.lower() not in ['host', 'connection', 'keep-alive', 'transfer-encoding']:
                    headers[key] = value
            
            # Prepare request data
            data = request.get_data()
            
            # Prepare query string
            query_string = request.query_string.decode('utf-8')
            if query_string:
                url += '?' + query_string
            
            # Make request with timeout
            timeout = self.config.get_connection_timeout()
            
            response = requests.request(
                method=request.method,
                url=url,
                headers=headers,
                data=data,
                timeout=timeout,
                allow_redirects=False
            )
            
            # Create Flask response
            flask_response = Response(
                response.content,
                status=response.status_code,
                headers=dict(response.headers)
            )
            
            return flask_response
            
        except requests.exceptions.Timeout:
            return handle_error(504, "Request timeout")
        except requests.exceptions.ConnectionError:
            return handle_error(502, "Connection error")
        except Exception as e:
            return handle_error(502, f"Error forwarding request: {str(e)}")

