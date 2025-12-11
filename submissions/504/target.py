"""
Target module.
Represents a single target (IP & port with optional base URI path).
"""
from typing import Optional
import threading
import time


class Target:
    """Represents a single target for HTTP requests."""
    
    def __init__(self, ip: str, port: int, base_uri: str = '/', weight: int = 1):
        """
        Initialize a target.
        
        Args:
            ip: The IP address of the target
            port: The port number of the target
            base_uri: The base URI path (default: '/')
        """
        self.ip = ip
        self.port = port
        self.base_uri = base_uri.rstrip('/') if base_uri != '/' else ''
        # Unique identifier for health check tracking
        self._id = id(self)
        # Weight used by weighted/LRT algorithms
        self.weight = max(1, int(weight)) if weight is not None else 1

        # Runtime metrics for LRT
        self.active_connections = 0
        self._ttfb_total = 0.0
        self._ttfb_count = 0
        self._lock = threading.Lock()
    
    def get_url(self, path: str) -> str:
        """
        Construct the full URL for a request to this target.
        
        Args:
            path: The request path (already rewritten)
            
        Returns:
            The full URL including base URI
        """
        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path
        
        # Combine base URI and path
        full_path = self.base_uri + path
        
        return f'http://{self.ip}:{self.port}{full_path}'
    
    def __repr__(self):
        return f'Target({self.ip}:{self.port}{self.base_uri}@w={self.weight})'

    def inc_connections(self):
        with self._lock:
            self.active_connections += 1

    def dec_connections(self):
        with self._lock:
            if self.active_connections > 0:
                self.active_connections -= 1

    def record_ttfb(self, ttfb_seconds: float):
        with self._lock:
            try:
                self._ttfb_total += float(ttfb_seconds)
                self._ttfb_count += 1
            except Exception:
                pass

    def avg_ttfb(self) -> float:
        with self._lock:
            if self._ttfb_count == 0:
                return 0.0
            return self._ttfb_total / self._ttfb_count

