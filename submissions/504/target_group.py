"""
Target Group module.
Represents a set of targets that can be load balanced.
"""
import socket
from typing import List, Optional, Dict
from target import Target


class TargetGroup:
    """Represents a group of targets for load balancing."""
    
    def __init__(self, name: str, targets_str: str, weights: Optional[Dict[str, int]] = None,
                 health_check_enabled: bool = False,
                 health_check_path: str = '/health',
                 health_check_interval_ms: int = 60000,
                 health_check_succeed_threshold: int = 2,
                 health_check_failure_threshold: int = 2):
        """
        Initialize a target group.
        
        Args:
            name: The name of the target group
            targets_str: Comma-delimited list of <hostname>:<port>/<base-uri> entries
            weights: Dictionary mapping hostname to weight (optional)
            health_check_enabled: Whether to enable health checks
            health_check_path: Path for health check requests
            health_check_interval_ms: Interval between health checks in milliseconds
            health_check_succeed_threshold: Consecutive successes to mark healthy
            health_check_failure_threshold: Consecutive failures to mark unhealthy
        """
        self.name = name
        # Store None explicitly to distinguish between "not provided" and "empty dict"
        self.weights = weights if weights is not None else {}
        self._weights_provided = weights is not None
        self.targets = self._parse_targets(targets_str)
        
        # Health check configuration
        self.health_check_enabled = health_check_enabled
        self.health_check_path = health_check_path
        self.health_check_interval_ms = health_check_interval_ms
        self.health_check_succeed_threshold = health_check_succeed_threshold
        self.health_check_failure_threshold = health_check_failure_threshold
        
        # Health check object (initialized lazily)
        self.health_check = None
    
    def _parse_targets(self, targets_str: str) -> List[Target]:
        """
        Parse targets from a comma-delimited string.
        Format: <hostname>:<port>/<base-uri>
        
        Args:
            targets_str: Comma-delimited list of target specifications
            
        Returns:
            List of Target objects
        """
        targets = []
        
        if not targets_str:
            return targets
        
        # Split by comma
        target_specs = [spec.strip() for spec in targets_str.split(',')]
        
        for spec in target_specs:
            if not spec:
                continue
            
            # Parse hostname:port/base-uri
            # First, check if there's a base URI
            if '/' in spec:
                # Split on the first / to separate address from base URI
                parts = spec.split('/', 1)
                address_part = parts[0]
                base_uri = '/' + parts[1] if parts[1] else '/'
            else:
                address_part = spec
                base_uri = '/'
            
            # Parse hostname:port
            if ':' in address_part:
                hostname, port_str = address_part.rsplit(':', 1)
                try:
                    port = int(port_str)
                except ValueError:
                    continue
            else:
                hostname = address_part
                port = 80  # Default HTTP port
            
            # Resolve DNS to get all IP addresses
            ip_addresses = self._resolve_dns(hostname)
            
            # Get weight from weights dict if available, otherwise default to 1
            weight = self.weights.get(hostname, 1) if self.weights else 1
            
            # Create a target for each IP address, preserving hostname for weight lookup
            for ip in ip_addresses:
                target = Target(ip, port, base_uri, hostname=hostname, weight=weight)
                targets.append(target)
        
        return targets
    
    def _resolve_dns(self, hostname: str) -> List[str]:
        """
        Resolve a hostname to one or more IP addresses.
        
        Args:
            hostname: The hostname to resolve
            
        Returns:
            List of IP addresses
        """
        ip_addresses = []
        
        try:
            # Try to resolve as IP address first
            socket.inet_aton(hostname)
            ip_addresses.append(hostname)
        except socket.error:
            # Not an IP address, try DNS resolution
            try:
                # Get all address info
                addr_infos = socket.getaddrinfo(hostname, None, socket.AF_INET)
                # Extract unique IP addresses
                seen_ips = set()
                for addr_info in addr_infos:
                    ip = addr_info[4][0]
                    if ip not in seen_ips:
                        seen_ips.add(ip)
                        ip_addresses.append(ip)
            except socket.gaierror:
                # DNS resolution failed
                pass
        
        return ip_addresses if ip_addresses else []
    
    def get_targets(self) -> List[Target]:
        """Get all targets in this group."""
        return self.targets
    
    def get_weight(self, hostname: str) -> int:
        """
        Get the weight for a hostname.
        
        Args:
            hostname: The hostname to get weight for
            
        Returns:
            The weight for the hostname, or 1 if not specified
        """
        return self.weights.get(hostname, 1) if self.weights else 1
    
    def get_weighted_target_list(self) -> List[Target]:
        """
        Get a list of targets expanded by their weights for weighted round-robin.
        Each target appears in the list a number of times equal to its weight.
        Weights are configured via TARGET_GROUP_<N>_WEIGHTS environment variable.
        
        Returns:
            List of targets expanded by weight, or empty list if no weights configured
        """
        # If weights were not provided via env var, return empty list
        if not self._weights_provided:
            return []
        
        weighted_list = []
        # Use target.weight directly - it's already set from weights dict during target creation
        for target in self.targets:
            # Add this target weight times
            for _ in range(target.weight):
                weighted_list.append(target)
        
        return weighted_list
    
    def get_healthy_targets(self) -> List[Target]:
        """
        Get only healthy targets from this group.
        If health checks are disabled, returns all targets.
        
        Returns:
            List of healthy targets
        """
        if not self.health_check_enabled or not self.health_check:
            return self.targets
        
        return self.health_check.get_healthy_targets(self.targets)
    
    def start_health_checks(self):
        """Start the health check thread for this target group."""
        # Early return if health checks are disabled or already running
        if not self.health_check_enabled:
            return
        
        if self.health_check:
            return
        
        from health_check import HealthCheck
        
        self.health_check = HealthCheck(
            target_group=self,
            enabled=self.health_check_enabled,
            path=self.health_check_path,
            interval_ms=self.health_check_interval_ms,
            succeed_threshold=self.health_check_succeed_threshold,
            failure_threshold=self.health_check_failure_threshold
        )
        self.health_check.start()
    
    def stop_health_checks(self):
        """Stop the health check thread for this target group."""
        if self.health_check:
            self.health_check.stop()

