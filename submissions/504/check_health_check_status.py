#!/usr/bin/env python3
"""
Quick script to check if health checks are enabled and running.
Run this to verify your configuration.

Usage:
    # With environment variables set:
    export TARGET_GROUP_1_NAME=backend
    export TARGET_GROUP_1_TARGETS=127.0.0.1:8081
    export TARGET_GROUP_1_HEALTH_CHECK_ENABLED=false
    python check_health_check_status.py
    
    # Or check environment variables only:
    python check_health_check_status.py --env-only
"""
import os
import sys
import argparse

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_env_vars():
    """Check environment variables directly."""
    print("=" * 60)
    print("Environment Variables Check")
    print("=" * 60)
    print()
    
    found_any = False
    for i in range(1, 20):  # Check up to 20 target groups
        name_key = f'TARGET_GROUP_{i}_NAME'
        enabled_key = f'TARGET_GROUP_{i}_HEALTH_CHECK_ENABLED'
        
        name = os.getenv(name_key)
        if name:
            found_any = True
            enabled = os.getenv(enabled_key, 'not set')
            print(f"Target Group {i}: {name}")
            print(f"  {enabled_key}: {enabled}")
            if enabled.lower() == 'true':
                print(f"  ⚠️  WARNING: Health checks are ENABLED")
            elif enabled.lower() == 'false':
                print(f"  ✓ Health checks are DISABLED")
            else:
                print(f"  ⚠️  WARNING: Variable not set (defaults to false)")
            print()
    
    if not found_any:
        print("No target group environment variables found.")
        print()
        print("Common variables to check:")
        print("  - TARGET_GROUP_1_NAME")
        print("  - TARGET_GROUP_1_TARGETS")
        print("  - TARGET_GROUP_1_HEALTH_CHECK_ENABLED")
        print()
        print("To see all environment variables:")
        print("  env | grep TARGET_GROUP")
    
    return found_any

def check_config():
    """Check configuration by loading Config."""
    try:
        from config import Config
        config = Config()
        
        print("=" * 60)
        print("Configuration Status (from Config class)")
        print("=" * 60)
        print()
        
        if not config.target_groups:
            print("No target groups configured.")
            print("This usually means environment variables are not set.")
            return False
        
        for name, target_group in config.target_groups.items():
            print(f"Target Group: {name}")
            print(f"  Health Check Enabled: {target_group.health_check_enabled}")
            
            # Check environment variable
            env_key = None
            for i in range(1, 20):
                if os.getenv(f'TARGET_GROUP_{i}_NAME') == name:
                    env_key = f'TARGET_GROUP_{i}_HEALTH_CHECK_ENABLED'
                    break
            
            if env_key:
                env_value = os.getenv(env_key, 'not set')
                print(f"  Environment Variable ({env_key}): {env_value}")
            else:
                print(f"  Environment Variable: not found")
            
            print(f"  Health Check Object: {target_group.health_check}")
            if target_group.health_check:
                print(f"    - Running: {target_group.health_check.running}")
                if target_group.health_check.thread:
                    print(f"    - Thread Alive: {target_group.health_check.thread.is_alive()}")
                    print(f"    - Thread Name: {target_group.health_check.thread.name}")
                print(f"    - Enabled: {target_group.health_check.enabled}")
                print(f"    ⚠️  WARNING: Health check thread is running!")
            else:
                print(f"    ✓ No health check object (health checks not started)")
            print()
        
        any_enabled = any(tg.health_check_enabled for tg in config.target_groups.values())
        any_running = any(tg.health_check and tg.health_check.running for tg in config.target_groups.values())
        
        print("=" * 60)
        print("Summary:")
        print("=" * 60)
        if any_enabled:
            print("⚠️  Health checks are ENABLED for at least one target group")
        else:
            print("✓ Health checks are DISABLED for all target groups")
        
        if any_running:
            print("⚠️  Health check threads are RUNNING")
            print("   To stop: Set TARGET_GROUP_<N>_HEALTH_CHECK_ENABLED=false and restart")
        else:
            print("✓ No health check threads are running")
        
        return True
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Check health check configuration status')
    parser.add_argument('--env-only', action='store_true', 
                       help='Only check environment variables, do not load Config')
    args = parser.parse_args()
    
    if args.env_only:
        check_env_vars()
    else:
        # Check both
        check_env_vars()
        print()
        print()
        check_config()
        print()
        print("=" * 60)
        print("Important Notes:")
        print("=" * 60)
        print("1. Configuration is read ONCE at application startup")
        print("2. You MUST restart the application after changing environment variables")
        print("3. If health checks are running, they will continue until restart")
        print("4. To verify running process, check with: ps aux | grep python")

if __name__ == '__main__':
    main()

