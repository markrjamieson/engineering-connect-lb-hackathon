"""
Health Check module.
Manages periodic health checks for targets in a target group.
"""
import requests
import threading
import time
from typing import Optional, Callable
from target import Target


class HealthCheck:
    """Manages health checks for a target group."""
    
    def __init__(self, 
                 target_group: 'TargetGroup',
                 enabled: bool,
                 path: str,
                 interval_ms: int,
                 succeed_threshold: int,
                 failure_threshold: int,
                 timeout_seconds: float = 5.0):
        """
        Initialize a health check.
        
        Args:
            target_group: Reference to the target group
            enabled: Whether health checks are enabled
            path: The path to health check (e.g., '/health')
            interval_ms: Interval between health checks in milliseconds
            succeed_threshold: Number of successful checks before marking healthy
            failure_threshold: Number of failed checks before marking unhealthy
            timeout_seconds: Timeout for health check requests
        """
        self.target_group = target_group
        self.enabled = enabled
        self.path = path
        self.interval = interval_ms / 1000.0  # Convert ms to seconds
        self.succeed_threshold = succeed_threshold
        self.failure_threshold = failure_threshold
        self.timeout = timeout_seconds
        
        # Target health tracking
        self.target_health = {}  # {target: {'consecutive_failures': int, 'consecutive_successes': int, 'healthy': bool}}
        
        # Thread control
        self.thread = None
        self.running = False
    
    def start(self):
        """Start the health check thread."""
        if not self.enabled:
            return
        
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the health check thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
    
    def _health_check_loop(self):
        """Main health check loop."""
        while self.running:
            try:
                # Check all targets
                targets = self.target_group.targets
                
                for target in targets:
                    if not self.running:
                        break
                    
                    self._check_target_health(target)
                
                # Sleep before next round of checks
                time.sleep(self.interval)
                
            except Exception as e:
                # Log error and continue
                print(f"Error in health check loop: {str(e)}")
                time.sleep(self.interval)
    
    def _check_target_health(self, target: Target):
        """
        Check the health of a single target.
        
        Args:
            target: The target to health check
        """
        # Initialize health tracking for this target if not already done
        if target not in self.target_health:
            self.target_health[target] = {
                'consecutive_failures': 0,
                'consecutive_successes': 0,
                'healthy': True  # Assume healthy initially
            }
        
        health_info = self.target_health[target]
        
        # Perform health check
        is_healthy = self._perform_health_check(target)
        
        if is_healthy:
            # Successful response
            health_info['consecutive_failures'] = 0
            health_info['consecutive_successes'] += 1
            
            # Mark as healthy if we've reached the threshold
            if health_info['consecutive_successes'] >= self.succeed_threshold:
                health_info['healthy'] = True
        else:
            # Failed response
            health_info['consecutive_successes'] = 0
            health_info['consecutive_failures'] += 1
            
            # Mark as unhealthy if we've reached the threshold
            if health_info['consecutive_failures'] >= self.failure_threshold:
                health_info['healthy'] = False
    
    def _perform_health_check(self, target: Target) -> bool:
        """
        Perform a single health check on a target.
        
        Args:
            target: The target to check
            
        Returns:
            True if health check passed (200 response), False otherwise
        """
        try:
            # Construct health check URL
            url = f'http://{target.ip}:{target.port}{self.path}'
            
            # Make GET request
            response = requests.get(url, timeout=self.timeout)
            
            # Only 200 is considered successful
            return response.status_code == 200
            
        except Exception:
            # Any error (timeout, connection error, etc.) is a failure
            return False
    
    def is_target_healthy(self, target: Target) -> bool:
        """
        Check if a target is currently healthy.
        
        Args:
            target: The target to check
            
        Returns:
            True if the target is healthy, False otherwise
        """
        if not self.enabled:
            # If health checks are disabled, all targets are considered healthy
            return True
        
        if target not in self.target_health:
            # Unknown target, assume healthy
            return True
        
        return self.target_health[target]['healthy']
    
    def get_healthy_targets(self, targets: list) -> list:
        """
        Filter targets to only include healthy ones.
        
        Args:
            targets: List of targets to filter
            
        Returns:
            List of healthy targets
        """
        if not self.enabled:
            return targets
        
        return [target for target in targets if self.is_target_healthy(target)]
