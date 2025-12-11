"""
Target module.
Represents a single target (IP & port with optional base URI path).
"""
from typing import Optional
import threading
import time
import collections


class Target:
    """Represents a single target for HTTP requests."""
    
    def __init__(self, ip: str, port: int, base_uri: str = '/', hostname: Optional[str] = None, weight: int = 1):
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
        self.hostname = hostname
        # Unique identifier for health check tracking
        self._id = id(self)
        # Weight used by weighted algorithm (configured via TARGET_GROUP_<N>_WEIGHTS env var)
        self.weight = max(1, int(weight)) if weight is not None else 1

        # Runtime metrics for LRT
        # Use atomic operations where possible to reduce lock contention
        self.active_connections = 0
        # Use deque with maxlen to limit memory usage and improve performance
        self._ttfb_samples = collections.deque(maxlen=1000)  # Keep last 1000 samples
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
        # Only show weight if it's not the default (1)
        weight_str = f', weight={self.weight}' if self.weight != 1 else ''
        return f'Target({self.ip}:{self.port}{self.base_uri}{weight_str})'

    def inc_connections(self):
        """Increment active connections counter (minimal lock time)."""
        with self._lock:
            self.active_connections += 1

    def dec_connections(self):
        """Decrement active connections counter (minimal lock time)."""
        with self._lock:
            if self.active_connections > 0:
                self.active_connections -= 1

    def record_ttfb(self, ttfb_seconds: float):
        """Record time-to-first-byte (optimized for high concurrency)."""
        try:
            # Append is thread-safe for deque, but we use lock for consistency
            # and to ensure atomic operation
            with self._lock:
                self._ttfb_samples.append(float(ttfb_seconds))
        except Exception:
            pass

    def avg_ttfb(self) -> float:
        """Calculate average time-to-first-byte (optimized)."""
        with self._lock:
            if not self._ttfb_samples:
                return 0.0
            # Use sum() which is faster than manual accumulation for deque
            return sum(self._ttfb_samples) / len(self._ttfb_samples)

