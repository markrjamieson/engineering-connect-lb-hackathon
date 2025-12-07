"""
Target module.
Represents a single target (IP & port with optional base URI path).
"""
from typing import Optional


class Target:
    """Represents a single target for HTTP requests."""
    
    def __init__(self, ip: str, port: int, base_uri: str = '/'):
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
        return f'Target({self.ip}:{self.port}{self.base_uri})'

