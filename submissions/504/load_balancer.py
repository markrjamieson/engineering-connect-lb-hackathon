"""
Load Balancer module.
Handles request forwarding and load balancing algorithms.
"""
import requests
import uuid
from flask import Request, Response
from typing import Optional, Dict, Tuple
from config import Config
from target_group import TargetGroup
from target import Target
from error_handler import handle_error
import time
import threading


# Hop-by-hop headers that should not be forwarded
HOP_BY_HOP_HEADERS = {'connection', 'keep-alive', 'transfer-encoding'}


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
        self.weighted_target_lists = {}  # Cache weighted target lists per target group
        self.weighted_counters = {}  # Track round robin state per target group
        # Session pool per target host for connection reuse
        self._sessions: Dict[str, requests.Session] = {}
        # Sticky session storage: {target_group_name: {client_ip: (target, expiration_time_ms)}}
        self.sticky_sessions: Dict[str, Dict[str, Tuple[Target, int]]] = {}
        self.sticky_lock = threading.Lock()  # Lock for sticky session access
    
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
            return self._weighted(target_group, targets)
        elif algorithm == 'STICKY':
            return self._sticky(target_group, targets, request)
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

    def _weighted(self, target_group: TargetGroup, targets: list) -> Target:
        """
        Select the next target using weighted round-robin algorithm.
        Targets are selected based on their weights, with higher weights
        receiving more requests proportionally.
        
        Args:
            target_group: The target group
            targets: List of available targets
            
        Returns:
            Selected target
        """
        group_name = target_group.name
        
        # Build or retrieve cached weighted target list
        if group_name not in self.weighted_target_lists:
            weighted_list = target_group.get_weighted_target_list()
            if not weighted_list:
                # Fallback to regular targets if no weights configured
                weighted_list = targets
            self.weighted_target_lists[group_name] = weighted_list
        
        weighted_list = self.weighted_target_lists[group_name]
        
        if not weighted_list:
            return targets[0] if targets else None
        
        # Initialize counter if not exists
        if group_name not in self.weighted_counters:
            self.weighted_counters[group_name] = 0
        
        # Get current index
        index = self.weighted_counters[group_name]
        
        # Select target from weighted list
        target = weighted_list[index % len(weighted_list)]
        
        # Increment counter for next request
        self.weighted_counters[group_name] = (index + 1) % len(weighted_list)
        
        return target
    
    def _least_response_time(self, target_group: TargetGroup, targets: list) -> Target:
        """
        Select the target with the lowest (active_connections * avg_ttfb).
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

            metric = active * avg

            if best is None or metric < best_metric:
                best = target
                best_metric = metric

        return best
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Get the client IP address from the request.
        Checks X-Forwarded-For header first, then access_route, then remote_addr.
        
        Args:
            request: The incoming Flask request
            
        Returns:
            Client IP address as string
        """
        # Check X-Forwarded-For header first
        x_forwarded_for = request.headers.get('X-Forwarded-For') or request.headers.get('x-forwarded-for')
        if x_forwarded_for:
            # Take the first IP (original client)
            client_ip = x_forwarded_for.split(',')[0].strip()
            if client_ip:
                return client_ip
        
        # Fall back to access_route or remote_addr
        if request.access_route:
            return request.access_route[0]
        return request.remote_addr or 'unknown'
    
    def _sticky(self, target_group: TargetGroup, targets: list, request: Request) -> Target:
        """
        Select a target using sticky session algorithm.
        Clients are assigned to the same target until the session TTL expires.
        After expiration, a new session is created using round-robin.
        
        Args:
            target_group: The target group
            targets: List of available targets
            request: The incoming request (for client identification)
            
        Returns:
            Selected target
        """
        group_name = target_group.name
        client_ip = self._get_client_ip(request)
        current_time_ms = int(time.time() * 1000)
        session_ttl_ms = self.config.get_session_ttl()
        
        with self.sticky_lock:
            # Initialize target group session storage if needed
            if group_name not in self.sticky_sessions:
                self.sticky_sessions[group_name] = {}
            
            group_sessions = self.sticky_sessions[group_name]
            
            # Check if client has an active session
            if client_ip in group_sessions:
                target, expiration_time = group_sessions[client_ip]
                
                # Check if session is still valid and target is still in healthy targets
                # Compare by IP and port since target objects might be different instances
                target_still_available = any(
                    t.ip == target.ip and t.port == target.port for t in targets
                )
                
                if current_time_ms < expiration_time and target_still_available:
                    # Find the actual target object from the current targets list
                    # to ensure we're using the latest target instance
                    for t in targets:
                        if t.ip == target.ip and t.port == target.port:
                            # Update stored target to current instance
                            group_sessions[client_ip] = (t, expiration_time)
                            return t
                else:
                    # Session expired or target no longer available, remove it
                    del group_sessions[client_ip]
            
            # No valid session exists, create new one using round-robin
            # Use round-robin to select next target
            selected_target = self._round_robin(target_group, targets)
            
            # Store new session with expiration time
            expiration_time = current_time_ms + session_ttl_ms
            group_sessions[client_ip] = (selected_target, expiration_time)
            
            return selected_target
    
    def _get_session(self, target: Target) -> requests.Session:
        """
        Get or create a session for the target host.
        Sessions are reused to enable connection pooling.
        
        Args:
            target: The target to get a session for
            
        Returns:
            A requests.Session configured for connection pooling
        """
        host_port = f"{target.ip}:{target.port}"
        if host_port not in self._sessions:
            session = requests.Session()
            # Disable proxy detection to avoid overhead
            session.trust_env = False
            # Configure connection pooling
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=10,  # Number of connection pools to cache
                pool_maxsize=20,      # Max connections per pool
                max_retries=0         # Disable retries for load balancer
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            self._sessions[host_port] = session
        return self._sessions[host_port]
    
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
            # Track connection and TTFB
            target.inc_connections()
            start = time.monotonic()
            
            # Construct full URL
            url = target.get_url(path)
            
            # Prepare request headers (exclude hop-by-hop headers)
            # Use set for O(1) lookup instead of list iteration
            headers = {
                key: value for key, value in request.headers
                if key.lower() not in HOP_BY_HOP_HEADERS
            }

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
            
            # Make request with timeout using connection pooling
            timeout = self.config.get_connection_timeout()
            session = self._get_session(target)
            
            response = session.request(
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

