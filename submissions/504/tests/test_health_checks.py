"""
Test health check functionality for target groups.

Tests cover:
- Health check configuration (enable, path, interval, thresholds)
- Periodic health check execution
- Target removal when health checks fail over threshold
- Target re-addition when health checks succeed over threshold
- Non-200 response codes are considered failures
- Only healthy targets receive traffic
"""
import pytest
import sys
import os
import time
import threading
import requests
from unittest.mock import Mock, MagicMock, patch
from flask import Flask, Response
from collections import Counter

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules
from config import Config
from load_balancer import LoadBalancer
from target_group import TargetGroup
from target import Target
from flask import Request


class MockHealthCheckServer:
    """A simple HTTP server for testing health checks."""
    
    def __init__(self, port, health_path='/health', health_status=200, delay_ms=0):
        """
        Initialize mock health check server.
        
        Args:
            port: Port to listen on
            health_path: Path that responds with health status
            health_status: HTTP status code for health endpoint
            delay_ms: Delay in milliseconds before responding
        """
        self.port = port
        self.health_path = health_path
        self.health_status = health_status
        self.delay_ms = delay_ms
        self.app = Flask(__name__)
        self.server_thread = None
        self.server = None
        self.request_count = 0
        self._lock = threading.Lock()
        
        @self.app.route('/', defaults={'path': ''}, methods=['GET'])
        @self.app.route('/<path:path>', methods=['GET'])
        def handle_request(path):
            """Handle all requests."""
            with self._lock:
                self.request_count += 1
                current_health_status = self.health_status
            
            full_path = f'/{path}' if path else '/'
            
            # Simulate delay
            if self.delay_ms > 0:
                time.sleep(self.delay_ms / 1000.0)
            
            # Health check endpoint
            if full_path == self.health_path:
                return Response('OK', status=current_health_status)
            
            # Regular endpoint
            return Response(f'{{"port": {self.port}, "path": "{full_path}"}}', 
                          status=200, mimetype='application/json')
    
    def start(self):
        """Start the server in a background thread."""
        from werkzeug.serving import make_server
        
        def run_server():
            self.server = make_server('127.0.0.1', self.port, self.app, threaded=True)
            self.server.serve_forever()
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        # Give server time to start
        time.sleep(0.5)
    
    def stop(self):
        """Stop the server."""
        if self.server:
            self.server.shutdown()
        if self.server_thread:
            self.server_thread.join(timeout=2.0)
    
    def set_health_status(self, status):
        """Change the health status code."""
        with self._lock:
            self.health_status = status


@pytest.fixture
def mock_config():
    """Create a mock Config object."""
    config = Mock(spec=Config)
    config.get_connection_timeout.return_value = 5.0
    config.get_load_balancing_algorithm.return_value = 'ROUND_ROBIN'
    return config


@pytest.fixture
def mock_request():
    """Create a mock Flask Request."""
    request = Mock(spec=Request)
    request.method = 'GET'
    request.headers = []
    request.get_data.return_value = b''
    request.query_string = b''
    return request


class TestHealthCheckConfiguration:
    """Test health check configuration parameters."""
    
    def test_health_check_disabled_by_default(self):
        """Test that health checks are disabled by default."""
        target_group = TargetGroup("backend", "127.0.0.1:8080")
        
        assert target_group.health_check_enabled is False
        assert target_group.health_check is None
    
    def test_health_check_enabled_configuration(self):
        """Test enabling health checks."""
        target_group = TargetGroup(
            "backend",
            "127.0.0.1:8080",
            health_check_enabled=True
        )
        
        assert target_group.health_check_enabled is True
    
    def test_health_check_path_configuration(self):
        """Test health check path configuration."""
        target_group = TargetGroup(
            "backend",
            "127.0.0.1:8080",
            health_check_enabled=True,
            health_check_path='/custom/health'
        )
        
        assert target_group.health_check_path == '/custom/health'
    
    def test_health_check_interval_configuration(self):
        """Test health check interval configuration."""
        target_group = TargetGroup(
            "backend",
            "127.0.0.1:8080",
            health_check_enabled=True,
            health_check_interval_ms=10000
        )
        
        assert target_group.health_check_interval_ms == 10000
    
    def test_health_check_succeed_threshold_configuration(self):
        """Test succeed threshold configuration."""
        target_group = TargetGroup(
            "backend",
            "127.0.0.1:8080",
            health_check_enabled=True,
            health_check_succeed_threshold=3
        )
        
        assert target_group.health_check_succeed_threshold == 3
    
    def test_health_check_failure_threshold_configuration(self):
        """Test failure threshold configuration."""
        target_group = TargetGroup(
            "backend",
            "127.0.0.1:8080",
            health_check_enabled=True,
            health_check_failure_threshold=3
        )
        
        assert target_group.health_check_failure_threshold == 3
    
    @patch.dict(os.environ, {
        'TARGET_GROUP_1_NAME': 'backend',
        'TARGET_GROUP_1_TARGETS': '127.0.0.1:8080',
        'TARGET_GROUP_1_HEALTH_CHECK_ENABLED': 'true',
        'TARGET_GROUP_1_HEALTH_CHECK_PATH': '/health',
        'TARGET_GROUP_1_HEALTH_CHECK_INTERVAL': '5000',
        'TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD': '2',
        'TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD': '2'
    })
    def test_config_parses_health_check_parameters(self):
        """Test that Config parses all health check parameters from environment."""
        config = Config()
        target_group = config.get_target_group('backend')
        
        assert target_group is not None
        assert target_group.health_check_enabled is True
        assert target_group.health_check_path == '/health'
        assert target_group.health_check_interval_ms == 5000
        assert target_group.health_check_succeed_threshold == 2
        assert target_group.health_check_failure_threshold == 2


class TestHealthCheckBasicFunctionality:
    """Test basic health check functionality."""
    
    def test_health_check_starts_when_enabled(self):
        """Test that health check thread starts when enabled."""
        target_group = TargetGroup(
            "backend",
            "127.0.0.1:8080",
            health_check_enabled=True,
            health_check_interval_ms=1000
        )
        
        target_group.start_health_checks()
        
        assert target_group.health_check is not None
        assert target_group.health_check.running is True
        assert target_group.health_check.thread is not None
        assert target_group.health_check.thread.is_alive()
        
        # Cleanup
        target_group.stop_health_checks()
    
    def test_health_check_does_not_start_when_disabled(self):
        """Test that health check thread does not start when disabled."""
        target_group = TargetGroup(
            "backend",
            "127.0.0.1:8080",
            health_check_enabled=False
        )
        
        target_group.start_health_checks()
        
        assert target_group.health_check is None
    
    def test_get_healthy_targets_returns_all_when_disabled(self):
        """Test that get_healthy_targets returns all targets when health checks disabled."""
        target_group = TargetGroup("backend", "127.0.0.1:8080,127.0.0.1:8081")
        targets = target_group.get_targets()
        
        healthy_targets = target_group.get_healthy_targets()
        
        assert len(healthy_targets) == len(targets)
        assert set(healthy_targets) == set(targets)
    
    def test_health_check_stops_cleanly(self):
        """Test that health check stops cleanly."""
        target_group = TargetGroup(
            "backend",
            "127.0.0.1:8080",
            health_check_enabled=True,
            health_check_interval_ms=1000
        )
        
        target_group.start_health_checks()
        assert target_group.health_check.running is True
        
        target_group.stop_health_checks()
        time.sleep(0.1)  # Give thread time to stop
        
        assert target_group.health_check.running is False


class TestHealthCheckResponseCodes:
    """Test that health checks handle different response codes correctly."""
    
    def test_200_response_is_considered_healthy(self):
        """Test that 200 response code is considered healthy."""
        from health_check import HealthCheck
        
        target = Target("127.0.0.1", 8080)
        target_group = Mock(spec=TargetGroup)
        target_group.targets = [target]
        
        # Mock requests.get to return 200
        with patch('health_check.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            health_check = HealthCheck(
                target_group=target_group,
                enabled=True,
                path='/health',
                interval_ms=1000,
                succeed_threshold=1,
                failure_threshold=1
            )
            
            is_healthy = health_check._perform_health_check(target)
            
            assert is_healthy is True
    
    def test_non_200_response_is_considered_unhealthy(self):
        """Test that non-200 response codes are considered unhealthy."""
        from health_check import HealthCheck
        
        target = Target("127.0.0.1", 8080)
        target_group = Mock(spec=TargetGroup)
        target_group.targets = [target]
        
        # Test various non-200 status codes
        for status_code in [400, 401, 403, 404, 500, 502, 503, 504]:
            with patch('health_check.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = status_code
                mock_get.return_value = mock_response
                
                health_check = HealthCheck(
                    target_group=target_group,
                    enabled=True,
                    path='/health',
                    interval_ms=1000,
                    succeed_threshold=1,
                    failure_threshold=1
                )
                
                is_healthy = health_check._perform_health_check(target)
                
                assert is_healthy is False, f"Status code {status_code} should be considered unhealthy"
    
    def test_connection_error_is_considered_unhealthy(self):
        """Test that connection errors are considered unhealthy."""
        from health_check import HealthCheck
        
        target = Target("127.0.0.1", 8080)
        target_group = Mock(spec=TargetGroup)
        target_group.targets = [target]
        
        # Mock requests.get to raise an exception
        with patch('health_check.requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
            
            health_check = HealthCheck(
                target_group=target_group,
                enabled=True,
                path='/health',
                interval_ms=1000,
                succeed_threshold=1,
                failure_threshold=1
            )
            
            is_healthy = health_check._perform_health_check(target)
            
            assert is_healthy is False
    
    def test_timeout_error_is_considered_unhealthy(self):
        """Test that timeout errors are considered unhealthy."""
        from health_check import HealthCheck
        
        target = Target("127.0.0.1", 8080)
        target_group = Mock(spec=TargetGroup)
        target_group.targets = [target]
        
        # Mock requests.get to raise a timeout
        with patch('health_check.requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
            
            health_check = HealthCheck(
                target_group=target_group,
                enabled=True,
                path='/health',
                interval_ms=1000,
                succeed_threshold=1,
                failure_threshold=1
            )
            
            is_healthy = health_check._perform_health_check(target)
            
            assert is_healthy is False


class TestHealthCheckThresholds:
    """Test health check threshold behavior."""
    
    def test_target_marked_unhealthy_after_failure_threshold(self):
        """Test that target is marked unhealthy after failure threshold is reached."""
        from health_check import HealthCheck
        
        target = Target("127.0.0.1", 8080)
        target_group = Mock(spec=TargetGroup)
        target_group.targets = [target]
        
        health_check = HealthCheck(
            target_group=target_group,
            enabled=True,
            path='/health',
            interval_ms=100,
            succeed_threshold=2,
            failure_threshold=3
        )
        
        # Initially healthy
        assert health_check.is_target_healthy(target) is True
        
        # Mock requests.get to return 500 (unhealthy)
        with patch('health_check.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response
            
            # Perform 3 failed checks (failure threshold)
            for _ in range(3):
                health_check._check_target_health(target)
            
            # Should now be unhealthy
            assert health_check.is_target_healthy(target) is False
    
    def test_target_marked_healthy_after_succeed_threshold(self):
        """Test that target is marked healthy after succeed threshold is reached."""
        from health_check import HealthCheck
        
        target = Target("127.0.0.1", 8080)
        target_group = Mock(spec=TargetGroup)
        target_group.targets = [target]
        
        health_check = HealthCheck(
            target_group=target_group,
            enabled=True,
            path='/health',
            interval_ms=100,
            succeed_threshold=2,
            failure_threshold=3
        )
        
        # First, mark it unhealthy
        health_check.target_health[target] = {
            'consecutive_failures': 3,
            'consecutive_successes': 0,
            'healthy': False
        }
        
        assert health_check.is_target_healthy(target) is False
        
        # Mock requests.get to return 200 (healthy)
        with patch('health_check.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Perform 2 successful checks (succeed threshold)
            for _ in range(2):
                health_check._check_target_health(target)
            
            # Should now be healthy
            assert health_check.is_target_healthy(target) is True
    
    def test_target_not_marked_unhealthy_before_threshold(self):
        """Test that target is not marked unhealthy before failure threshold."""
        from health_check import HealthCheck
        
        target = Target("127.0.0.1", 8080)
        target_group = Mock(spec=TargetGroup)
        target_group.targets = [target]
        
        health_check = HealthCheck(
            target_group=target_group,
            enabled=True,
            path='/health',
            interval_ms=100,
            succeed_threshold=2,
            failure_threshold=3
        )
        
        # Mock requests.get to return 500 (unhealthy)
        with patch('health_check.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response
            
            # Perform only 2 failed checks (below threshold)
            for _ in range(2):
                health_check._check_target_health(target)
            
            # Should still be healthy (below threshold)
            assert health_check.is_target_healthy(target) is True


class TestHealthCheckPeriodicExecution:
    """Test that health checks run periodically."""
    
    def test_health_check_runs_periodically(self):
        """Test that health checks execute at the configured interval."""
        from health_check import HealthCheck
        
        target = Target("127.0.0.1", 8080)
        target_group = Mock(spec=TargetGroup)
        target_group.targets = [target]
        
        check_times = []
        
        def mock_get(*args, **kwargs):
            check_times.append(time.time())
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response
        
        health_check = HealthCheck(
            target_group=target_group,
            enabled=True,
            path='/health',
            interval_ms=500,  # 500ms interval
            succeed_threshold=1,
            failure_threshold=1
        )
        
        with patch('health_check.requests.get', side_effect=mock_get):
            health_check.start()
            
            # Wait for at least 2 checks
            time.sleep(1.2)
            
            health_check.stop()
            
            # Should have at least 2 checks
            assert len(check_times) >= 2
            
            # Check that intervals are approximately correct (allow some variance)
            if len(check_times) >= 2:
                intervals = [check_times[i+1] - check_times[i] for i in range(len(check_times)-1)]
                avg_interval = sum(intervals) / len(intervals)
                # Should be around 0.5 seconds, allow 20% variance
                assert 0.4 <= avg_interval <= 0.6


class TestHealthCheckIntegration:
    """Integration tests with real HTTP servers."""
    
    def test_only_healthy_targets_receive_traffic(self, mock_config, mock_request):
        """Test that only healthy targets receive traffic."""
        # Start two mock servers
        server1 = MockHealthCheckServer(8081, health_status=200)
        server2 = MockHealthCheckServer(8082, health_status=500)  # Unhealthy
        
        try:
            server1.start()
            server2.start()
            time.sleep(0.5)  # Give servers time to start
            
            # Create target group with health checks enabled
            target_group = TargetGroup(
                "backend",
                "127.0.0.1:8081,127.0.0.1:8082",
                health_check_enabled=True,
                health_check_path='/health',
                health_check_interval_ms=500,
                health_check_succeed_threshold=1,
                health_check_failure_threshold=1
            )
            
            target_group.start_health_checks()
            
            # Wait for initial health checks
            time.sleep(1.0)
            
            load_balancer = LoadBalancer(mock_config)
            
            # Make multiple requests
            selected_targets = []
            for _ in range(10):
                target = load_balancer.select_target(target_group, mock_request)
                if target:
                    selected_targets.append(target.port)
            
            # All requests should go to the healthy server (port 8081)
            assert all(port == 8081 for port in selected_targets)
            
            target_group.stop_health_checks()
            
        finally:
            server1.stop()
            server2.stop()
    
    def test_unhealthy_target_removed_after_threshold(self, mock_config, mock_request):
        """Test that unhealthy target is removed after failure threshold."""
        # Start two mock servers, both initially healthy
        server1 = MockHealthCheckServer(8081, health_status=200)
        server2 = MockHealthCheckServer(8082, health_status=200)
        
        try:
            server1.start()
            server2.start()
            time.sleep(0.5)
            
            # Create target group with health checks
            target_group = TargetGroup(
                "backend",
                "127.0.0.1:8081,127.0.0.1:8082",
                health_check_enabled=True,
                health_check_path='/health',
                health_check_interval_ms=300,
                health_check_succeed_threshold=1,
                health_check_failure_threshold=2
            )
            
            target_group.start_health_checks()
            
            # Wait for initial health checks
            time.sleep(0.5)
            
            load_balancer = LoadBalancer(mock_config)
            
            # Initially, both servers should receive traffic
            selected_ports = []
            for _ in range(10):
                target = load_balancer.select_target(target_group, mock_request)
                if target:
                    selected_ports.append(target.port)
            
            assert 8081 in selected_ports
            assert 8082 in selected_ports
            
            # Make server2 unhealthy
            server2.set_health_status(500)
            
            # Wait for health checks to detect failure (2 failures needed)
            time.sleep(1.0)
            
            # Now only server1 should receive traffic
            selected_ports_after = []
            for _ in range(10):
                target = load_balancer.select_target(target_group, mock_request)
                if target:
                    selected_ports_after.append(target.port)
            
            assert all(port == 8081 for port in selected_ports_after)
            
            target_group.stop_health_checks()
            
        finally:
            server1.stop()
            server2.stop()
    
    def test_unhealthy_target_re_added_after_recovery(self, mock_config, mock_request):
        """Test that unhealthy target is re-added after recovery."""
        # Start two mock servers
        server1 = MockHealthCheckServer(8081, health_status=200)
        server2 = MockHealthCheckServer(8082, health_status=500)  # Initially unhealthy
        
        try:
            server1.start()
            server2.start()
            time.sleep(0.5)
            
            # Create target group with health checks
            target_group = TargetGroup(
                "backend",
                "127.0.0.1:8081,127.0.0.1:8082",
                health_check_enabled=True,
                health_check_path='/health',
                health_check_interval_ms=300,
                health_check_succeed_threshold=2,
                health_check_failure_threshold=2
            )
            
            target_group.start_health_checks()
            
            # Wait for health checks to mark server2 as unhealthy
            time.sleep(1.0)
            
            load_balancer = LoadBalancer(mock_config)
            
            # Initially, only server1 should receive traffic
            selected_ports = []
            for _ in range(10):
                target = load_balancer.select_target(target_group, mock_request)
                if target:
                    selected_ports.append(target.port)
            
            assert all(port == 8081 for port in selected_ports)
            
            # Make server2 healthy again
            server2.set_health_status(200)
            
            # Wait for health checks to detect recovery (2 successes needed)
            time.sleep(1.0)
            
            # Now both servers should receive traffic
            selected_ports_after = []
            for _ in range(10):
                target = load_balancer.select_target(target_group, mock_request)
                if target:
                    selected_ports_after.append(target.port)
            
            assert 8081 in selected_ports_after
            assert 8082 in selected_ports_after
            
            target_group.stop_health_checks()
            
        finally:
            server1.stop()
            server2.stop()
    
    def test_custom_health_check_path(self, mock_config, mock_request):
        """Test that custom health check path is used."""
        # Start server with health endpoint at /custom/health
        server = MockHealthCheckServer(8081, health_path='/custom/health', health_status=200)
        
        try:
            server.start()
            time.sleep(0.5)
            
            # Create target group with custom health check path
            target_group = TargetGroup(
                "backend",
                "127.0.0.1:8081",
                health_check_enabled=True,
                health_check_path='/custom/health',
                health_check_interval_ms=500,
                health_check_succeed_threshold=1,
                health_check_failure_threshold=1
            )
            
            target_group.start_health_checks()
            
            # Wait for health check
            time.sleep(0.8)
            
            # Target should be healthy
            healthy_targets = target_group.get_healthy_targets()
            assert len(healthy_targets) == 1
            
            target_group.stop_health_checks()
            
        finally:
            server.stop()


class TestHealthCheckWithMultipleTargets:
    """Test health checks with multiple targets."""
    
    def test_multiple_targets_health_check_independently(self, mock_config, mock_request):
        """Test that multiple targets are health checked independently."""
        # Start three mock servers
        server1 = MockHealthCheckServer(8081, health_status=200)
        server2 = MockHealthCheckServer(8082, health_status=500)  # Unhealthy
        server3 = MockHealthCheckServer(8083, health_status=200)
        
        try:
            server1.start()
            server2.start()
            server3.start()
            time.sleep(0.5)
            
            # Create target group with health checks
            target_group = TargetGroup(
                "backend",
                "127.0.0.1:8081,127.0.0.1:8082,127.0.0.1:8083",
                health_check_enabled=True,
                health_check_path='/health',
                health_check_interval_ms=300,
                health_check_succeed_threshold=1,
                health_check_failure_threshold=1
            )
            
            target_group.start_health_checks()
            
            # Wait for health checks
            time.sleep(0.8)
            
            load_balancer = LoadBalancer(mock_config)
            
            # Only healthy servers (8081 and 8083) should receive traffic
            selected_ports = []
            for _ in range(20):
                target = load_balancer.select_target(target_group, mock_request)
                if target:
                    selected_ports.append(target.port)
            
            assert 8081 in selected_ports
            assert 8083 in selected_ports
            assert 8082 not in selected_ports
            
            target_group.stop_health_checks()
            
        finally:
            server1.stop()
            server2.stop()
            server3.stop()

