"""
Target Group module.
Represents a set of targets that can be load balanced.
"""
import socket
from typing import List, Optional
from target import Target


class TargetGroup:
    """Represents a group of targets for load balancing."""
    
    def __init__(self, name: str, targets_str: str, 
                 health_check_enabled: bool = False,
                 health_check_path: str = '/health',
                 health_check_interval_ms: int = 30000,
                 health_check_succeed_threshold: int = 2,
                 health_check_failure_threshold: int = 2):
        """
        Initialize a target group.
        
        Args:
            name: The name of the target group
            targets_str: Comma-delimited list of <hostname>:<port>/<base-uri> entries
            health_check_enabled: Whether to enable health checks
            health_check_path: Path for health check requests
            health_check_interval_ms: Interval between health checks in milliseconds
            health_check_succeed_threshold: Consecutive successes to mark healthy
            health_check_failure_threshold: Consecutive failures to mark unhealthy
        """
        self.name = name
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
            # Allow optional weight suffix using '@', e.g. host:port/path@2
            weight = 1
            if '@' in spec:
                try:
                    spec, weight_str = spec.rsplit('@', 1)
                    weight = int(weight_str)
                except Exception:
                    weight = 1
            
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
            
            # Create a target for each IP address
            for ip in ip_addresses:
                target = Target(ip, port, base_uri, weight=weight)
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
        if not self.health_check_enabled or self.health_check:
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

