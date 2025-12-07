"""
Listener Rule module.
Represents a mapping from a URI on the load balancer to a target group.
"""
from typing import Optional


class ListenerRule:
    """Represents a listener rule with path prefix, rewrite, and target group."""
    
    def __init__(self, path_prefix: str, path_rewrite: str, target_group: str):
        """
        Initialize a listener rule.
        
        Args:
            path_prefix: The prefix to match against incoming HTTP URIs
            path_rewrite: The prefix to strip from the URI before forwarding
            target_group: The target group name to route requests to
        """
        self.path_prefix = path_prefix
        self.path_rewrite = path_rewrite
        self.target_group = target_group
    
    def rewrite_uri(self, uri: str) -> str:
        """
        Rewrite the URI by stripping the path_rewrite prefix if configured.
        
        Args:
            uri: The original URI
            
        Returns:
            The rewritten URI
        """
        if self.path_rewrite and uri.startswith(self.path_rewrite):
            # Strip the rewrite prefix
            rewritten = uri[len(self.path_rewrite):]
            # Ensure it starts with /
            if not rewritten.startswith('/'):
                rewritten = '/' + rewritten
            return rewritten
        return uri

