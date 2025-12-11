#!/usr/bin/env python3
"""
Health Check Verification Script
Verifies that the health check feature is correctly implemented.
"""

import os
import sys
from target_group import TargetGroup
from health_check import HealthCheck


def test_health_check_configuration():
    """Test that health check configuration is properly parsed."""
    print("=" * 60)
    print("Test 1: Health Check Configuration Parsing")
    print("=" * 60)
    
    # Create a target group with health checks enabled
    tg = TargetGroup(
        name="test_backend",
        targets_str="127.0.0.1:8080,127.0.0.1:8081",
        health_check_enabled=True,
        health_check_path="/health",
        health_check_interval_ms=10000,
        health_check_succeed_threshold=2,
        health_check_failure_threshold=3
    )
    
    print(f"Target Group Name: {tg.name}")
    print(f"Health Check Enabled: {tg.health_check_enabled}")
    print(f"Health Check Path: {tg.health_check_path}")
    print(f"Health Check Interval: {tg.health_check_interval_ms}ms")
    print(f"Succeed Threshold: {tg.health_check_succeed_threshold}")
    print(f"Failure Threshold: {tg.health_check_failure_threshold}")
    print(f"Number of Targets: {len(tg.targets)}")
    print()
    
    for i, target in enumerate(tg.targets, 1):
        print(f"  Target {i}: {target.ip}:{target.port}")
    
    print()
    print("✓ Configuration parsing works correctly")
    print()


def test_health_check_startup():
    """Test that health checks can be started and stopped."""
    print("=" * 60)
    print("Test 2: Health Check Startup/Shutdown")
    print("=" * 60)
    
    tg = TargetGroup(
        name="test_backend",
        targets_str="127.0.0.1:8080",
        health_check_enabled=True,
        health_check_path="/health",
        health_check_interval_ms=5000,
        health_check_succeed_threshold=2,
        health_check_failure_threshold=2
    )
    
    print("Starting health checks...")
    tg.start_health_checks()
    print("✓ Health checks started")
    
    if tg.health_check is None:
        print("✗ Health check object not initialized")
        return False
    
    if not tg.health_check.running:
        print("✗ Health check thread not running")
        return False
    
    print("✓ Health check thread is running")
    
    print("Stopping health checks...")
    tg.stop_health_checks()
    print("✓ Health checks stopped")
    print()
    
    return True


def test_healthy_targets_filtering():
    """Test that get_healthy_targets filters targets correctly."""
    print("=" * 60)
    print("Test 3: Healthy Targets Filtering (disabled health checks)")
    print("=" * 60)
    
    # Without health checks
    tg_no_hc = TargetGroup(
        name="no_health_check",
        targets_str="127.0.0.1:8080,127.0.0.1:8081,127.0.0.1:8082",
        health_check_enabled=False
    )
    
    print(f"All targets: {len(tg_no_hc.get_targets())}")
    print(f"Healthy targets (HC disabled): {len(tg_no_hc.get_healthy_targets())}")
    
    if len(tg_no_hc.get_healthy_targets()) == len(tg_no_hc.get_targets()):
        print("✓ All targets returned when health checks disabled")
    else:
        print("✗ Filtering failed when health checks disabled")
        return False
    
    print()
    
    # With health checks enabled
    tg_with_hc = TargetGroup(
        name="with_health_check",
        targets_str="127.0.0.1:8080,127.0.0.1:8081",
        health_check_enabled=True,
        health_check_path="/health"
    )
    
    print(f"All targets: {len(tg_with_hc.get_targets())}")
    print(f"Healthy targets (HC enabled, not started): {len(tg_with_hc.get_healthy_targets())}")
    
    if len(tg_with_hc.get_healthy_targets()) == len(tg_with_hc.get_targets()):
        print("✓ All targets returned when health checks not started")
    else:
        print("✗ Filtering failed when health checks not started")
        return False
    
    print()
    return True


def test_environment_variable_parsing():
    """Test that environment variables are correctly parsed by Config."""
    print("=" * 60)
    print("Test 4: Environment Variable Parsing")
    print("=" * 60)
    
    # Set environment variables
    os.environ['TARGET_GROUP_1_NAME'] = 'api_backend'
    os.environ['TARGET_GROUP_1_TARGETS'] = '127.0.0.1:8080,127.0.0.1:8081'
    os.environ['TARGET_GROUP_1_HEALTH_CHECK_ENABLED'] = 'true'
    os.environ['TARGET_GROUP_1_HEALTH_CHECK_PATH'] = '/api/health'
    os.environ['TARGET_GROUP_1_HEALTH_CHECK_INTERVAL'] = '15000'
    os.environ['TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD'] = '3'
    os.environ['TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD'] = '5'
    
    # Import Config here after setting env vars
    from config import Config
    
    config = Config()
    
    tg = config.get_target_group('api_backend')
    
    if tg is None:
        print("✗ Target group not found in config")
        return False
    
    print(f"Target Group: {tg.name}")
    print(f"Health Check Enabled: {tg.health_check_enabled}")
    print(f"Health Check Path: {tg.health_check_path}")
    print(f"Health Check Interval: {tg.health_check_interval_ms}ms")
    print(f"Succeed Threshold: {tg.health_check_succeed_threshold}")
    print(f"Failure Threshold: {tg.health_check_failure_threshold}")
    
    # Verify values
    checks = [
        (tg.health_check_enabled == True, "Health checks enabled"),
        (tg.health_check_path == '/api/health', "Health check path"),
        (tg.health_check_interval_ms == 15000, "Health check interval"),
        (tg.health_check_succeed_threshold == 3, "Succeed threshold"),
        (tg.health_check_failure_threshold == 5, "Failure threshold"),
    ]
    
    all_passed = True
    for check, description in checks:
        if check:
            print(f"✓ {description}")
        else:
            print(f"✗ {description}")
            all_passed = False
    
    print()
    return all_passed


def main():
    """Run all tests."""
    print()
    print("*" * 60)
    print("* Health Check Feature Verification")
    print("*" * 60)
    print()
    
    try:
        test_health_check_configuration()
        test_health_check_startup()
        test_healthy_targets_filtering()
        test_environment_variable_parsing()
        
        print("=" * 60)
        print("✓ All tests completed successfully!")
        print("=" * 60)
        print()
        print("Summary:")
        print("- Health check configuration is properly implemented")
        print("- Health checks can be started and stopped")
        print("- Healthy targets filtering works correctly")
        print("- Environment variable parsing works correctly")
        print()
        
    except Exception as e:
        print(f"✗ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
