"""
Configuration module for the load balancer.
Handles environment variable parsing and configuration management.
"""
import os
import socket
from typing import List, Dict, Optional
from target_group import TargetGroup
from listener_rule import ListenerRule


class Config:
    """Manages load balancer configuration from environment variables."""
    
    def __init__(self):
        self.listener_port = int(os.getenv('LISTENER_PORT', '8080'))
        self.connection_timeout = int(os.getenv('CONNECTION_TIMEOUT', '5000')) / 1000.0  # Convert ms to seconds
        # Allowed values: ROUND_ROBIN, WEIGHTED, STICKY, LRT
        self.load_balancing_algorithm = os.getenv('LOAD_BALANCING_ALGORITHM', 'ROUND_ROBIN')
        self.header_convention_enable = os.getenv('HEADER_CONVENTION_ENABLE', 'false').lower() == 'true'
        
        # Parse listener rules
        self.listener_rules = self._parse_listener_rules()
        
        # Parse target groups
        self.target_groups = self._parse_target_groups()
    
    def get_listener_port(self) -> int:
        """Get the listener port."""
        return self.listener_port
    
    def get_connection_timeout(self) -> float:
        """Get the connection timeout in seconds."""
        return self.connection_timeout
    
    def get_load_balancing_algorithm(self) -> str:
        """Get the load balancing algorithm."""
        return self.load_balancing_algorithm

    def get_header_convention_enable(self) -> bool:
        """Return whether to add convention headers (e.g., X-Forwarded-*)."""
        return self.header_convention_enable
    
    def _parse_listener_rules(self) -> List[ListenerRule]:
        """
        Parse listener rules from environment variables.
        Expected format: LISTENER_RULE_<N>_PATH_PREFIX, LISTENER_RULE_<N>_PATH_REWRITE, LISTENER_RULE_<N>_TARGET_GROUP
        """
        rules = []
        rule_index = 1
        
        while True:
            path_prefix_key = f'LISTENER_RULE_{rule_index}_PATH_PREFIX'
            path_rewrite_key = f'LISTENER_RULE_{rule_index}_PATH_REWRITE'
            target_group_key = f'LISTENER_RULE_{rule_index}_TARGET_GROUP'
            
            path_prefix = os.getenv(path_prefix_key)
            if not path_prefix:
                break
            
            path_rewrite = os.getenv(path_rewrite_key, '')
            target_group = os.getenv(target_group_key)
            
            if target_group:
                rule = ListenerRule(path_prefix, path_rewrite, target_group)
                rules.append(rule)
            
            rule_index += 1
        
        # Sort by path prefix length (longest first) for proper matching
        rules.sort(key=lambda r: len(r.path_prefix), reverse=True)
        
        return rules
    
    def _parse_target_groups(self) -> Dict[str, TargetGroup]:
        """
        Parse target groups from environment variables.
        Expected format: TARGET_GROUP_<N>_NAME, TARGET_GROUP_<N>_TARGETS,
                       TARGET_GROUP_<N>_HEALTH_CHECK_ENABLED, etc.
        """
        target_groups = {}
        group_index = 1
        
        while True:
            name_key = f'TARGET_GROUP_{group_index}_NAME'
            targets_key = f'TARGET_GROUP_{group_index}_TARGETS'
            
            name = os.getenv(name_key)
            if not name:
                break
            
            targets_str = os.getenv(targets_key, '')
            
            # Parse health check configuration
            health_check_enabled_key = f'TARGET_GROUP_{group_index}_HEALTH_CHECK_ENABLED'
            health_check_path_key = f'TARGET_GROUP_{group_index}_HEALTH_CHECK_PATH'
            health_check_interval_key = f'TARGET_GROUP_{group_index}_HEALTH_CHECK_INTERVAL'
            health_check_succeed_threshold_key = f'TARGET_GROUP_{group_index}_HEALTH_CHECK_SUCCEED_THRESHOLD'
            health_check_failure_threshold_key = f'TARGET_GROUP_{group_index}_HEALTH_CHECK_FAILURE_THRESHOLD'
            
            # Parse with defaults
            health_check_enabled = os.getenv(health_check_enabled_key, 'false').lower() == 'true'
            health_check_path = os.getenv(health_check_path_key, '/health')
            health_check_interval = int(os.getenv(health_check_interval_key, '60000'))
            health_check_succeed_threshold = int(os.getenv(health_check_succeed_threshold_key, '2'))
            health_check_failure_threshold = int(os.getenv(health_check_failure_threshold_key, '2'))
            
            if targets_str:
                target_group = TargetGroup(
                    name, 
                    targets_str,
                    health_check_enabled=health_check_enabled,
                    health_check_path=health_check_path,
                    health_check_interval_ms=health_check_interval,
                    health_check_succeed_threshold=health_check_succeed_threshold,
                    health_check_failure_threshold=health_check_failure_threshold
                )
                target_groups[name] = target_group
            
            group_index += 1
        
        return target_groups
    
    def find_listener_rule(self, path: str) -> Optional[ListenerRule]:
        """
        Find the first listener rule that matches the given path.
        Returns None if no rule matches.
        """
        for rule in self.listener_rules:
            if path.startswith(rule.path_prefix):
                return rule
        return None
    
    def get_target_group(self, name: str) -> Optional[TargetGroup]:
        """Get a target group by name."""
        return self.target_groups.get(name)

