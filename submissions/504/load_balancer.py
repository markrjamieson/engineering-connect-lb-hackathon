"""
Load Balancer module.
Handles request forwarding and load balancing algorithms.
"""
import requests
import uuid
import time
from flask import Request, Response
from typing import Optional, Dict
from config import Config
from target_group import TargetGroup
from target import Target
from error_handler import handle_error
import time


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
        self.sticky_sessions: Dict[str, Dict] = {}  # Track sticky sessions: {client_id: {target: Target, expires_at: float}}
    
    def select_target(self, target_group: TargetGroup, request: Request) -> Optional[Target]:
        """
        Select a target from the target group using the configured algorithm.
        Only selects from healthy targets if health checks are enabled.
        
        Args:
            target_group: The target group to select from
            request: The incoming request (for sticky sessions, etc.)
            
        Returns:
            Selected target or None if no targets available
        """
        # Get healthy targets (or all targets if health checks disabled)
        targets = target_group.get_healthy_targets()
        
        if not targets:
            return None
        
        algorithm = self.config.get_load_balancing_algorithm()
        
        if algorithm == 'ROUND_ROBIN':
            return self._round_robin(target_group, targets)
        elif algorithm == 'LRT':
            return self._least_response_time(target_group, targets)
        elif algorithm == 'WEIGHTED':
            # Not implemented yet
            return targets[0] if targets else None
        elif algorithm == 'STICKY':
            return self._sticky_session(target_group, targets, request)
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

    def _least_response_time(self, target_group: TargetGroup, targets: list) -> Target:
        """
        Select the target with the lowest (active_connections * avg_ttfb / weight).
        If avg_ttfb is unknown (0), it's treated as a small value to prefer idle targets.
        """
        best = None
        best_metric = None
        for target in targets:
            # get metrics
            active = getattr(target, 'active_connections', 0)
            avg_ttfb = getattr(target, 'avg_ttfb', None)
            try:
                avg = target.avg_ttfb() if callable(target.avg_ttfb) else 0.0
            except Exception:
                avg = 0.0

            if avg <= 0.0:
                # treat unknown avg as very small to favor cold targets
                avg = 0.001

            weight = getattr(target, 'weight', 1) or 1

            metric = (active * avg) / float(weight)

            if best is None or metric < best_metric:
                best = target
                best_metric = metric

        return best
    
    def _get_client_id(self, request: Request) -> str:
        """
        Get a unique identifier for the client.
        Uses IP address from X-Forwarded-For header or remote address.
        
        Args:
            request: The incoming request
            
        Returns:
            Client identifier string
        """
        # Try to get client IP from X-Forwarded-For header first
        x_forwarded_for = request.headers.get('X-Forwarded-For')
        if x_forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            client_ip = x_forwarded_for.split(',')[0].strip()
        else:
            # Fall back to remote address
            client_ip = request.access_route[0] if request.access_route else request.remote_addr
        
        return client_ip or 'unknown'
    
    def _sticky_session(self, target_group: TargetGroup, targets: list, request: Request) -> Target:
        """
        Select a target using sticky session algorithm.
        Clients are assigned to the same target until TTL expires.
        After expiration, a new session is created using round-robin.
        
        Args:
            target_group: The target group
            targets: List of available targets
            request: The incoming request
            
        Returns:
            Selected target
        """
        client_id = self._get_client_id(request)
        session_key = f"{target_group.name}:{client_id}"
        current_time = time.time()
        
        # Check if there's an existing valid session
        if session_key in self.sticky_sessions:
            session = self.sticky_sessions[session_key]
            # Check if session is still valid
            if current_time < session['expires_at']:
                # Session is still valid, return the same target
                return session['target']
            else:
                # Session expired, remove it
                del self.sticky_sessions[session_key]
        
        # No valid session exists, create a new one using round-robin
        target = self._round_robin(target_group, targets)
        
        # Create new session with TTL
        session_ttl = self.config.get_session_ttl()
        self.sticky_sessions[session_key] = {
            'target': target,
            'expires_at': current_time + session_ttl
        }
        
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

            # Add X-Forwarded-* headers when enabled
            if self.config.get_header_convention_enable():
                # Determine client IP (prefer the first element in access_route)
                client_ip = request.access_route[0] if request.access_route else request.remote_addr

                # X-Forwarded-For: append client IP if already present
                existing_xff = headers.get('X-Forwarded-For') or headers.get('x-forwarded-for')
                if existing_xff and client_ip:
                    headers['X-Forwarded-For'] = f"{existing_xff}, {client_ip}"
                elif client_ip:
                    headers['X-Forwarded-For'] = client_ip

                # X-Forwarded-Host: set to requested host
                if request.host:
                    headers['X-Forwarded-Host'] = request.host

                # X-Forwarded-Port: set to listener port
                headers['X-Forwarded-Port'] = str(self.config.get_listener_port())

                # X-Forwarded-Proto: set to request scheme (http/https)
                headers['X-Forwarded-Proto'] = request.scheme

                # X-Real-IP: set to client IP
                if client_ip:
                    headers['X-Real-IP'] = client_ip

                # X-Request-Id: generate unique request ID
                headers['X-Request-Id'] = str(uuid.uuid4())

                # Host: set to original host header (override the excluded host)
                if request.host:
                    headers['Host'] = request.host
            
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
                allow_redirects=False,
                stream=True
            )

            ttfb = time.monotonic() - start
            try:
                target.record_ttfb(ttfb)
            except Exception:
                pass

            # Read body to completion
            content = response.content

            flask_response = Response(
                content,
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
        finally:
            try:
                target.dec_connections()
            except Exception:
                pass

