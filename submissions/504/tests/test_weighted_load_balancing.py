"""
Test weighted load balancing functionality.

Tests cover:
- Weight configuration parsing
- Weight validation (all targets must have weights)
- Weighted request distribution
- Edge cases (single target, equal weights, DNS resolution)
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from collections import Counter

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules
from config import Config
from load_balancer import LoadBalancer
from target_group import TargetGroup
from target import Target
from flask import Request


class TestWeightParsing:
    """Test weight configuration parsing."""
    
    def test_parse_weights_single_target(self):
        """Test parsing weights for a single target."""
        config = Config()
        weights = config._parse_weights("target1.com:5")
        
        assert weights == {"target1.com": 5}
    
    def test_parse_weights_multiple_targets(self):
        """Test parsing weights for multiple targets."""
        config = Config()
        weights = config._parse_weights("target1.com:1,target2.com:2,target3.com:5")
        
        assert weights == {"target1.com": 1, "target2.com": 2, "target3.com": 5}
    
    def test_parse_weights_with_spaces(self):
        """Test parsing weights with spaces around values."""
        config = Config()
        weights = config._parse_weights("target1.com : 1 , target2.com : 2")
        
        assert weights == {"target1.com": 1, "target2.com": 2}
    
    def test_parse_weights_empty_string(self):
        """Test parsing empty weights string returns None."""
        config = Config()
        weights = config._parse_weights("")
        
        assert weights is None
    
    def test_parse_weights_none(self):
        """Test parsing None weights returns None."""
        config = Config()
        weights = config._parse_weights(None)
        
        assert weights is None
    
    def test_parse_weights_invalid_format(self):
        """Test parsing invalid weight format raises error."""
        config = Config()
        
        with pytest.raises(ValueError, match="Invalid weight format"):
            config._parse_weights("target1.com")
    
    def test_parse_weights_invalid_weight_value(self):
        """Test parsing invalid weight value raises error."""
        config = Config()
        
        with pytest.raises(ValueError, match="Invalid weight format"):
            config._parse_weights("target1.com:abc")
    
    def test_parse_weights_zero_weight(self):
        """Test that weight must be >= 1."""
        config = Config()
        
        with pytest.raises(ValueError, match="Weight must be >= 1"):
            config._parse_weights("target1.com:0")
    
    def test_parse_weights_negative_weight(self):
        """Test that negative weights are rejected."""
        config = Config()
        
        with pytest.raises(ValueError, match="Weight must be >= 1"):
            config._parse_weights("target1.com:-1")


class TestWeightValidation:
    """Test weight validation."""
    
    def test_validate_weights_all_targets_have_weights(self):
        """Test validation passes when all targets have weights."""
        config = Config()
        targets_str = "target1.com:8080,target2.com:8080"
        weights = {"target1.com": 1, "target2.com": 2}
        
        # Should not raise
        config._validate_weights("backend", targets_str, weights)
    
    def test_validate_weights_missing_weight_raises_error(self):
        """Test validation raises error when target is missing weight."""
        config = Config()
        targets_str = "target1.com:8080,target2.com:8080"
        weights = {"target1.com": 1}  # target2.com missing
        
        with pytest.raises(ValueError, match="Missing weights for"):
            config._validate_weights("backend", targets_str, weights)
    
    def test_validate_weights_with_base_uri(self):
        """Test validation works with base URI in target spec."""
        config = Config()
        targets_str = "target1.com:8080/api,target2.com:8080/v1"
        weights = {"target1.com": 1, "target2.com": 2}
        
        # Should not raise
        config._validate_weights("backend", targets_str, weights)
    
    def test_validate_weights_with_ip_address(self):
        """Test validation works with IP addresses."""
        config = Config()
        targets_str = "127.0.0.1:8080,192.168.1.1:8080"
        weights = {"127.0.0.1": 1, "192.168.1.1": 2}
        
        # Should not raise
        config._validate_weights("backend", targets_str, weights)
    
    def test_validate_weights_empty_targets(self):
        """Test validation with empty targets string."""
        config = Config()
        weights = {}
        
        # Should not raise
        config._validate_weights("backend", "", weights)


class TestWeightedTargetGroup:
    """Test TargetGroup with weights."""
    
    def test_target_group_with_weights(self):
        """Test TargetGroup stores weights correctly."""
        weights = {"target1.com": 1, "target2.com": 2}
        target_group = TargetGroup("backend", "target1.com:8080,target2.com:8080", weights)
        
        assert target_group.weights == weights
    
    def test_target_group_get_weight(self):
        """Test getting weight for a hostname."""
        weights = {"target1.com": 1, "target2.com": 2}
        target_group = TargetGroup("backend", "target1.com:8080,target2.com:8080", weights)
        
        assert target_group.get_weight("target1.com") == 1
        assert target_group.get_weight("target2.com") == 2
    
    def test_target_group_get_weight_default(self):
        """Test getting weight defaults to 1 if not specified."""
        target_group = TargetGroup("backend", "target1.com:8080")
        
        assert target_group.get_weight("target1.com") == 1
        assert target_group.get_weight("nonexistent.com") == 1
    
    @patch('target_group.TargetGroup._resolve_dns')
    def test_get_weighted_target_list_simple(self, mock_resolve_dns):
        """Test building weighted target list with simple weights."""
        mock_resolve_dns.side_effect = lambda h: ["127.0.0.1"] if h == "target1.com" else ["127.0.0.2"]
        
        weights = {"target1.com": 1, "target2.com": 2}
        target_group = TargetGroup("backend", "target1.com:8080,target2.com:8080", weights)
        
        weighted_list = target_group.get_weighted_target_list()
        
        # Should have 3 targets total (1 + 2)
        assert len(weighted_list) == 3
        # Count occurrences
        hostnames = [t.hostname for t in weighted_list]
        assert hostnames.count("target1.com") == 1
        assert hostnames.count("target2.com") == 2
    
    @patch('target_group.TargetGroup._resolve_dns')
    def test_get_weighted_target_list_multiple_ips(self, mock_resolve_dns):
        """Test weighted list when hostname resolves to multiple IPs."""
        def resolve_side_effect(hostname):
            if hostname == "target1.com":
                return ["127.0.0.1", "127.0.0.2"]  # 2 IPs
            else:
                return ["127.0.0.3"]
        
        mock_resolve_dns.side_effect = resolve_side_effect
        
        weights = {"target1.com": 2, "target2.com": 1}
        target_group = TargetGroup("backend", "target1.com:8080,target2.com:8080", weights)
        
        weighted_list = target_group.get_weighted_target_list()
        
        # target1.com has weight 2 and 2 IPs = 4 entries
        # target2.com has weight 1 and 1 IP = 1 entry
        # Total: 5 entries
        assert len(weighted_list) == 5
        
        # Count by hostname
        hostnames = [t.hostname for t in weighted_list]
        assert hostnames.count("target1.com") == 4
        assert hostnames.count("target2.com") == 1
    
    @patch('target_group.TargetGroup._resolve_dns')
    def test_get_weighted_target_list_equal_weights(self, mock_resolve_dns):
        """Test weighted list with equal weights (should behave like round-robin)."""
        mock_resolve_dns.side_effect = lambda h: ["127.0.0.1"] if h == "target1.com" else ["127.0.0.2"]
        
        weights = {"target1.com": 1, "target2.com": 1}
        target_group = TargetGroup("backend", "target1.com:8080,target2.com:8080", weights)
        
        weighted_list = target_group.get_weighted_target_list()
        
        # Should have 2 targets (1 + 1)
        assert len(weighted_list) == 2
        hostnames = [t.hostname for t in weighted_list]
        assert hostnames.count("target1.com") == 1
        assert hostnames.count("target2.com") == 1
    
    @patch('target_group.TargetGroup._resolve_dns')
    def test_get_weighted_target_list_no_weights(self, mock_resolve_dns):
        """Test weighted list when no weights are configured."""
        mock_resolve_dns.side_effect = lambda h: ["127.0.0.1"] if h == "target1.com" else ["127.0.0.2"]
        
        target_group = TargetGroup("backend", "target1.com:8080,target2.com:8080")
        
        weighted_list = target_group.get_weighted_target_list()
        
        # Should return empty list (no weights configured)
        assert len(weighted_list) == 0


class TestWeightedLoadBalancer:
    """Test LoadBalancer with weighted algorithm."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock Config with weighted algorithm."""
        config = Mock(spec=Config)
        config.get_load_balancing_algorithm.return_value = 'WEIGHTED'
        config.get_connection_timeout.return_value = 5.0
        return config
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock Flask Request."""
        request = Mock(spec=Request)
        request.method = 'GET'
        request.headers = []
        request.get_data.return_value = b''
        request.query_string = b''
        return request
    
    @patch('target_group.TargetGroup._resolve_dns')
    def test_weighted_selection_1_to_2_ratio(self, mock_resolve_dns, mock_config, mock_request):
        """Test weighted selection with 1:2 weight ratio."""
        mock_resolve_dns.side_effect = lambda h: ["127.0.0.1"] if h == "target1.com" else ["127.0.0.2"]
        
        weights = {"target1.com": 1, "target2.com": 2}
        target_group = TargetGroup("backend", "target1.com:8080,target2.com:8080", weights)
        
        load_balancer = LoadBalancer(mock_config)
        
        # Make 9 selections (should get 3:6 ratio)
        selections = []
        for _ in range(9):
            target = load_balancer.select_target(target_group, mock_request)
            selections.append(target.hostname)
        
        # Count selections
        counts = Counter(selections)
        # Should be approximately 1:2 ratio (3:6)
        assert counts["target1.com"] == 3
        assert counts["target2.com"] == 6
    
    @patch('target_group.TargetGroup._resolve_dns')
    def test_weighted_selection_1_to_2_to_5_ratio(self, mock_resolve_dns, mock_config, mock_request):
        """Test weighted selection with 1:2:5 weight ratio."""
        def resolve_side_effect(hostname):
            mapping = {
                "target1.com": ["127.0.0.1"],
                "target2.com": ["127.0.0.2"],
                "target3.com": ["127.0.0.3"]
            }
            return mapping.get(hostname, [])
        
        mock_resolve_dns.side_effect = resolve_side_effect
        
        weights = {"target1.com": 1, "target2.com": 2, "target3.com": 5}
        target_group = TargetGroup(
            "backend",
            "target1.com:8080,target2.com:8080,target3.com:8080",
            weights
        )
        
        load_balancer = LoadBalancer(mock_config)
        
        # Make 16 selections (should get 2:4:10 ratio)
        selections = []
        for _ in range(16):
            target = load_balancer.select_target(target_group, mock_request)
            selections.append(target.hostname)
        
        # Count selections
        counts = Counter(selections)
        # Should be approximately 1:2:5 ratio (2:4:10)
        assert counts["target1.com"] == 2
        assert counts["target2.com"] == 4
        assert counts["target3.com"] == 10
    
    @patch('target_group.TargetGroup._resolve_dns')
    def test_weighted_selection_round_robin_behavior(self, mock_resolve_dns, mock_config, mock_request):
        """Test that weighted selection cycles through the weighted list correctly."""
        mock_resolve_dns.side_effect = lambda h: ["127.0.0.1"] if h == "target1.com" else ["127.0.0.2"]
        
        weights = {"target1.com": 1, "target2.com": 2}
        target_group = TargetGroup("backend", "target1.com:8080,target2.com:8080", weights)
        
        load_balancer = LoadBalancer(mock_config)
        
        # Make 6 selections - should cycle: target1, target2, target2, target1, target2, target2
        selections = []
        for _ in range(6):
            target = load_balancer.select_target(target_group, mock_request)
            selections.append(target.hostname)
        
        # Verify the pattern
        assert selections == ["target1.com", "target2.com", "target2.com", 
                             "target1.com", "target2.com", "target2.com"]
    
    @patch('target_group.TargetGroup._resolve_dns')
    def test_weighted_selection_no_weights_fallback(self, mock_resolve_dns, mock_config, mock_request):
        """Test that weighted selection falls back to regular targets if no weights."""
        mock_resolve_dns.side_effect = lambda h: ["127.0.0.1"] if h == "target1.com" else ["127.0.0.2"]
        
        target_group = TargetGroup("backend", "target1.com:8080,target2.com:8080")
        
        load_balancer = LoadBalancer(mock_config)
        
        # Should still work, just uses regular targets
        target = load_balancer.select_target(target_group, mock_request)
        assert target is not None
        assert target.hostname in ["target1.com", "target2.com"]
    
    @patch('target_group.TargetGroup._resolve_dns')
    def test_weighted_selection_single_target(self, mock_resolve_dns, mock_config, mock_request):
        """Test weighted selection with single target."""
        mock_resolve_dns.return_value = ["127.0.0.1"]
        
        weights = {"target1.com": 5}
        target_group = TargetGroup("backend", "target1.com:8080", weights)
        
        load_balancer = LoadBalancer(mock_config)
        
        # All selections should be target1.com
        for _ in range(10):
            target = load_balancer.select_target(target_group, mock_request)
            assert target.hostname == "target1.com"


class TestWeightedConfigIntegration:
    """Test weighted configuration with environment variables."""
    
    @patch.dict(os.environ, {
        'TARGET_GROUP_1_NAME': 'backend',
        'TARGET_GROUP_1_TARGETS': 'target1.com:8080,target2.com:8080',
        'TARGET_GROUP_1_WEIGHTS': 'target1.com:1,target2.com:2',
        'LOAD_BALANCING_ALGORITHM': 'WEIGHTED'
    })
    @patch('target_group.TargetGroup._resolve_dns')
    def test_config_with_weights(self, mock_resolve_dns):
        """Test Config parsing with weights."""
        mock_resolve_dns.side_effect = lambda h: ["127.0.0.1"] if h == "target1.com" else ["127.0.0.2"]
        
        config = Config()
        
        assert config.get_load_balancing_algorithm() == 'WEIGHTED'
        target_group = config.get_target_group('backend')
        assert target_group is not None
        assert target_group.weights == {"target1.com": 1, "target2.com": 2}
    
    @patch.dict(os.environ, {
        'TARGET_GROUP_1_NAME': 'backend',
        'TARGET_GROUP_1_TARGETS': 'target1.com:8080,target2.com:8080',
        'TARGET_GROUP_1_WEIGHTS': 'target1.com:1',  # Missing target2.com
        'LOAD_BALANCING_ALGORITHM': 'WEIGHTED'
    })
    @patch('target_group.TargetGroup._resolve_dns')
    def test_config_missing_weight_raises_error(self, mock_resolve_dns):
        """Test Config raises error when weight is missing."""
        mock_resolve_dns.side_effect = lambda h: ["127.0.0.1"] if h == "target1.com" else ["127.0.0.2"]
        
        with pytest.raises(ValueError, match="Missing weights for"):
            Config()
    
    @patch.dict(os.environ, {
        'TARGET_GROUP_1_NAME': 'backend',
        'TARGET_GROUP_1_TARGETS': 'target1.com:8080,target2.com:8080',
        'LOAD_BALANCING_ALGORITHM': 'WEIGHTED'
        # Missing TARGET_GROUP_1_WEIGHTS
    })
    @patch('target_group.TargetGroup._resolve_dns')
    def test_config_weighted_algorithm_requires_weights(self, mock_resolve_dns):
        """Test Config raises error when WEIGHTED algorithm used without weights."""
        mock_resolve_dns.side_effect = lambda h: ["127.0.0.1"] if h == "target1.com" else ["127.0.0.2"]
        
        with pytest.raises(ValueError, match="does not have.*WEIGHTS configured"):
            Config()
    
    @patch.dict(os.environ, {
        'TARGET_GROUP_1_NAME': 'backend',
        'TARGET_GROUP_1_TARGETS': 'target1.com:8080,target2.com:8080',
        'TARGET_GROUP_1_WEIGHTS': 'target1.com:1,target2.com:2',
        'LOAD_BALANCING_ALGORITHM': 'ROUND_ROBIN'
    })
    @patch('target_group.TargetGroup._resolve_dns')
    def test_config_weights_optional_for_round_robin(self, mock_resolve_dns):
        """Test that weights are optional when using ROUND_ROBIN algorithm."""
        mock_resolve_dns.side_effect = lambda h: ["127.0.0.1"] if h == "target1.com" else ["127.0.0.2"]
        
        # Should not raise error
        config = Config()
        assert config.get_load_balancing_algorithm() == 'ROUND_ROBIN'

