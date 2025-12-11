"""
Test error handling requirements for the load balancer.

Tests cover:
- 404: No listener rule matched
- 502: Connection errors
- 503: No targets available
- 504: Request timeouts
- Upstream errors returned unchanged
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from flask import Flask
import requests
from requests.exceptions import Timeout, ConnectionError

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the app and modules
from app import app
from config import Config
from load_balancer import LoadBalancer
from target_group import TargetGroup
from target import Target
from listener_rule import ListenerRule
from error_handler import handle_error


@pytest.fixture
def client():
    """Create a Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_config():
    """Create a mock Config object."""
    config = Mock(spec=Config)
    config.listener_rules = []
    config.target_groups = {}
    config.get_connection_timeout.return_value = 5.0
    config.get_load_balancing_algorithm.return_value = 'ROUND_ROBIN'
    return config


@pytest.fixture
def mock_listener_rule():
    """Create a mock ListenerRule."""
    rule = Mock(spec=ListenerRule)
    rule.path_prefix = '/api'
    rule.path_rewrite = ''
    rule.target_group = 'backend'
    rule.rewrite_uri = Mock(return_value='/api/test')
    return rule


@pytest.fixture
def mock_target_group():
    """Create a mock TargetGroup with targets."""
    target_group = Mock(spec=TargetGroup)
    target_group.name = 'backend'
    mock_target = Mock(spec=Target)
    mock_target.get_url.return_value = 'http://127.0.0.1:8080/api/test'
    target_group.get_targets.return_value = [mock_target]
    return target_group


class Test404ErrorHandling:
    """Test 404 error: No listener rule matched."""
    
    def test_404_no_listener_rule_matched(self, client, mock_config, mock_listener_rule):
        """Test that 404 is returned with empty payload when no listener rule matches."""
        # Setup: No matching listener rule
        mock_config.find_listener_rule.return_value = None
        
        # Patch the config in app module
        with patch('app.config', mock_config):
            response = client.get('/nonexistent/path')
            
            # Assert 404 status code
            assert response.status_code == 404
            # Assert empty payload
            assert response.data == b''
    
    def test_404_empty_path_no_rule(self, client, mock_config):
        """Test 404 for root path when no root rule exists."""
        mock_config.find_listener_rule.return_value = None
        
        with patch('app.config', mock_config):
            response = client.get('/')
            
            assert response.status_code == 404
            assert response.data == b''


class Test502ErrorHandling:
    """Test 502 error: Connection errors."""
    
    def test_502_connection_error_in_forward_request(self, client, mock_config, 
                                                      mock_listener_rule, mock_target_group):
        """Test 502 when connection error occurs during request forwarding."""
        # Setup: Valid listener rule and target group
        mock_config.find_listener_rule.return_value = mock_listener_rule
        mock_config.get_target_group.return_value = mock_target_group
        
        # Mock LoadBalancer to raise ConnectionError
        mock_load_balancer = Mock(spec=LoadBalancer)
        mock_load_balancer.select_target.return_value = mock_target_group.get_targets()[0]
        mock_load_balancer.forward_request.side_effect = ConnectionError("Connection refused")
        
        with patch('app.config', mock_config), \
             patch('app.load_balancer', mock_load_balancer):
            response = client.get('/api/test')
            
            assert response.status_code == 502
            assert response.data == b''
    
    def test_502_generic_exception_in_proxy(self, client, mock_config, mock_listener_rule, 
                                            mock_target_group):
        """Test 502 when generic exception occurs in proxy endpoint."""
        # Setup: Valid listener rule and target group
        mock_config.find_listener_rule.return_value = mock_listener_rule
        mock_config.get_target_group.return_value = mock_target_group
        
        # Mock LoadBalancer to raise generic exception
        mock_load_balancer = Mock(spec=LoadBalancer)
        mock_load_balancer.select_target.side_effect = Exception("Unexpected error")
        
        with patch('app.config', mock_config), \
             patch('app.load_balancer', mock_load_balancer):
            response = client.get('/api/test')
            
            assert response.status_code == 502
            assert response.data == b''


class Test503ErrorHandling:
    """Test 503 error: No targets available."""
    
    def test_503_target_group_not_found(self, client, mock_config, mock_listener_rule):
        """Test 503 when target group is not found."""
        # Setup: Valid listener rule but no target group
        mock_config.find_listener_rule.return_value = mock_listener_rule
        mock_config.get_target_group.return_value = None
        
        with patch('app.config', mock_config):
            response = client.get('/api/test')
            
            assert response.status_code == 503
            assert response.data == b''
    
    def test_503_no_targets_available_empty_list(self, client, mock_config, 
                                                  mock_listener_rule, mock_target_group):
        """Test 503 when target group exists but has no targets."""
        # Setup: Valid listener rule and target group, but empty targets list
        mock_config.find_listener_rule.return_value = mock_listener_rule
        mock_config.get_target_group.return_value = mock_target_group
        mock_target_group.get_targets.return_value = []
        
        with patch('app.config', mock_config):
            response = client.get('/api/test')
            
            assert response.status_code == 503
            assert response.data == b''
    
    def test_503_no_target_selected(self, client, mock_config, mock_listener_rule, 
                                     mock_target_group):
        """Test 503 when load balancer cannot select a target."""
        # Setup: Valid listener rule and target group with targets
        mock_config.find_listener_rule.return_value = mock_listener_rule
        mock_config.get_target_group.return_value = mock_target_group
        
        # Mock LoadBalancer to return None for select_target
        mock_load_balancer = Mock(spec=LoadBalancer)
        mock_load_balancer.select_target.return_value = None
        
        with patch('app.config', mock_config), \
             patch('app.load_balancer', mock_load_balancer):
            response = client.get('/api/test')
            
            assert response.status_code == 503
            assert response.data == b''


class Test504ErrorHandling:
    """Test 504 error: Request timeouts."""
    
    def test_504_timeout_error(self, client, mock_config, mock_listener_rule, mock_target_group):
        """Test 504 when request times out."""
        # Setup: Valid listener rule and target group
        mock_config.find_listener_rule.return_value = mock_listener_rule
        mock_config.get_target_group.return_value = mock_target_group
        
        # Mock LoadBalancer to return 504 response (forward_request handles Timeout internally)
        from flask import Response
        mock_load_balancer = Mock(spec=LoadBalancer)
        mock_load_balancer.select_target.return_value = mock_target_group.get_targets()[0]
        # forward_request catches Timeout and returns 504 Response
        mock_load_balancer.forward_request.return_value = Response('', status=504)
        
        with patch('app.config', mock_config), \
             patch('app.load_balancer', mock_load_balancer):
            response = client.get('/api/test')
            
            assert response.status_code == 504
            assert response.data == b''


class TestUpstreamErrorHandling:
    """Test that upstream errors are returned unchanged."""
    
    def test_upstream_400_error_returned_unchanged(self, client, mock_config, 
                                                     mock_listener_rule, mock_target_group):
        """Test that 400 from upstream is returned with original payload."""
        # Setup: Valid listener rule and target group
        mock_config.find_listener_rule.return_value = mock_listener_rule
        mock_config.get_target_group.return_value = mock_target_group
        
        # Create a mock response from upstream
        mock_upstream_response = Mock()
        mock_upstream_response.status_code = 400
        mock_upstream_response.content = b'{"error": "Bad Request"}'
        mock_upstream_response.headers = {'Content-Type': 'application/json'}
        
        # Mock LoadBalancer to return upstream response
        mock_load_balancer = Mock(spec=LoadBalancer)
        mock_load_balancer.select_target.return_value = mock_target_group.get_targets()[0]
        
        # Mock Flask Response from forward_request
        from flask import Response
        flask_response = Response(
            mock_upstream_response.content,
            status=mock_upstream_response.status_code,
            headers=dict(mock_upstream_response.headers)
        )
        mock_load_balancer.forward_request.return_value = flask_response
        
        with patch('app.config', mock_config), \
             patch('app.load_balancer', mock_load_balancer):
            response = client.get('/api/test')
            
            # Assert status code is unchanged
            assert response.status_code == 400
            # Assert payload is unchanged
            assert response.data == b'{"error": "Bad Request"}'
            # Assert headers are preserved
            assert response.headers.get('Content-Type') == 'application/json'
    
    def test_upstream_500_error_returned_unchanged(self, client, mock_config, 
                                                     mock_listener_rule, mock_target_group):
        """Test that 500 from upstream is returned with original payload."""
        # Setup: Valid listener rule and target group
        mock_config.find_listener_rule.return_value = mock_listener_rule
        mock_config.get_target_group.return_value = mock_target_group
        
        # Create a mock response from upstream
        mock_upstream_response = Mock()
        mock_upstream_response.status_code = 500
        mock_upstream_response.content = b'Internal Server Error'
        mock_upstream_response.headers = {'Content-Type': 'text/plain'}
        
        # Mock LoadBalancer to return upstream response
        mock_load_balancer = Mock(spec=LoadBalancer)
        mock_load_balancer.select_target.return_value = mock_target_group.get_targets()[0]
        
        from flask import Response
        flask_response = Response(
            mock_upstream_response.content,
            status=mock_upstream_response.status_code,
            headers=dict(mock_upstream_response.headers)
        )
        mock_load_balancer.forward_request.return_value = flask_response
        
        with patch('app.config', mock_config), \
             patch('app.load_balancer', mock_load_balancer):
            response = client.get('/api/test')
            
            # Assert status code is unchanged
            assert response.status_code == 500
            # Assert payload is unchanged
            assert response.data == b'Internal Server Error'
            # Assert headers are preserved
            assert response.headers.get('Content-Type') == 'text/plain'
    
    def test_upstream_401_error_returned_unchanged(self, client, mock_config, 
                                                     mock_listener_rule, mock_target_group):
        """Test that 401 from upstream is returned with original payload."""
        # Setup: Valid listener rule and target group
        mock_config.find_listener_rule.return_value = mock_listener_rule
        mock_config.get_target_group.return_value = mock_target_group
        
        # Create a mock response from upstream
        mock_upstream_response = Mock()
        mock_upstream_response.status_code = 401
        mock_upstream_response.content = b'Unauthorized'
        mock_upstream_response.headers = {'WWW-Authenticate': 'Basic realm="API"'}
        
        # Mock LoadBalancer to return upstream response
        mock_load_balancer = Mock(spec=LoadBalancer)
        mock_load_balancer.select_target.return_value = mock_target_group.get_targets()[0]
        
        from flask import Response
        flask_response = Response(
            mock_upstream_response.content,
            status=mock_upstream_response.status_code,
            headers=dict(mock_upstream_response.headers)
        )
        mock_load_balancer.forward_request.return_value = flask_response
        
        with patch('app.config', mock_config), \
             patch('app.load_balancer', mock_load_balancer):
            response = client.get('/api/test')
            
            # Assert status code is unchanged
            assert response.status_code == 401
            # Assert payload is unchanged
            assert response.data == b'Unauthorized'
            # Assert headers are preserved
            assert response.headers.get('WWW-Authenticate') == 'Basic realm="API"'
    
    def test_upstream_403_error_with_json_payload(self, client, mock_config, 
                                                    mock_listener_rule, mock_target_group):
        """Test that 403 from upstream is returned with original JSON payload."""
        # Setup: Valid listener rule and target group
        mock_config.find_listener_rule.return_value = mock_listener_rule
        mock_config.get_target_group.return_value = mock_target_group
        
        # Create a mock response from upstream with JSON
        json_payload = b'{"error": "Forbidden", "message": "Access denied"}'
        mock_upstream_response = Mock()
        mock_upstream_response.status_code = 403
        mock_upstream_response.content = json_payload
        mock_upstream_response.headers = {'Content-Type': 'application/json'}
        
        # Mock LoadBalancer to return upstream response
        mock_load_balancer = Mock(spec=LoadBalancer)
        mock_load_balancer.select_target.return_value = mock_target_group.get_targets()[0]
        
        from flask import Response
        flask_response = Response(
            mock_upstream_response.content,
            status=mock_upstream_response.status_code,
            headers=dict(mock_upstream_response.headers)
        )
        mock_load_balancer.forward_request.return_value = flask_response
        
        with patch('app.config', mock_config), \
             patch('app.load_balancer', mock_load_balancer):
            response = client.get('/api/test')
            
            # Assert status code is unchanged
            assert response.status_code == 403
            # Assert JSON payload is unchanged
            assert response.data == json_payload
            assert response.headers.get('Content-Type') == 'application/json'


class TestLoadBalancerErrorHandling:
    """Test error handling in LoadBalancer.forward_request directly."""
    
    def test_load_balancer_timeout_exception(self, mock_config):
        """Test that LoadBalancer raises 504 on timeout."""
        from load_balancer import LoadBalancer
        
        load_balancer = LoadBalancer(mock_config)
        mock_target = Mock(spec=Target)
        mock_target.get_url.return_value = 'http://127.0.0.1:8080/test'
        
        mock_request = Mock()
        mock_request.method = 'GET'
        mock_request.headers = [('Content-Type', 'application/json')]
        mock_request.get_data.return_value = b''
        mock_request.query_string = b''
        
        # Mock requests.request to raise Timeout
        with patch('load_balancer.requests.request') as mock_requests:
            mock_requests.side_effect = Timeout("Request timed out")
            
            response = load_balancer.forward_request(mock_target, mock_request, '/test')
            
            assert response.status_code == 504
            assert response.data == b''
    
    def test_load_balancer_connection_error(self, mock_config):
        """Test that LoadBalancer returns 502 on connection error."""
        from load_balancer import LoadBalancer
        
        load_balancer = LoadBalancer(mock_config)
        mock_target = Mock(spec=Target)
        mock_target.get_url.return_value = 'http://127.0.0.1:8080/test'
        
        mock_request = Mock()
        mock_request.method = 'GET'
        mock_request.headers = [('Content-Type', 'application/json')]
        mock_request.get_data.return_value = b''
        mock_request.query_string = b''
        
        # Mock requests.request to raise ConnectionError
        with patch('load_balancer.requests.request') as mock_requests:
            mock_requests.side_effect = ConnectionError("Connection refused")
            
            response = load_balancer.forward_request(mock_target, mock_request, '/test')
            
            assert response.status_code == 502
            assert response.data == b''
    
    def test_load_balancer_upstream_418_returned_unchanged(self, mock_config):
        """Test that LoadBalancer returns upstream 418 (I'm a teapot) unchanged."""
        from load_balancer import LoadBalancer
        import requests
        
        load_balancer = LoadBalancer(mock_config)
        mock_target = Mock(spec=Target)
        mock_target.get_url.return_value = 'http://127.0.0.1:8080/test'
        
        mock_request = Mock()
        mock_request.method = 'GET'
        mock_request.headers = [('Content-Type', 'application/json')]
        mock_request.get_data.return_value = b''
        mock_request.query_string = b''
        
        # Mock requests.response with 418 status
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 418
        mock_response.content = b"I'm a teapot"
        mock_response.headers = {'Content-Type': 'text/plain'}
        
        with patch('load_balancer.requests.request') as mock_requests:
            mock_requests.return_value = mock_response
            
            response = load_balancer.forward_request(mock_target, mock_request, '/test')
            
            assert response.status_code == 418
            assert response.data == b"I'm a teapot"
            assert response.headers.get('Content-Type') == 'text/plain'

