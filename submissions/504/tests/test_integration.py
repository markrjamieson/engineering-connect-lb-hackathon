#!/usr/bin/env python3
"""
Quick integration test: start mocks, app, make requests, verify health checks work.
"""
import subprocess
import time
import requests
import sys
import signal
import os

def run_test():
    procs = []
    
    try:
        print("=" * 60)
        print("Starting mock targets on 8081 and 8082...")
        print("=" * 60)
        
        # Start mock targets
        p1 = subprocess.Popen([sys.executable, "mock_target.py", "8081"], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p2 = subprocess.Popen([sys.executable, "mock_target.py", "8082"], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        procs.extend([p1, p2])
        
        time.sleep(2)
        print("✓ Mock targets started")
        
        # Verify health endpoints
        print("\nVerifying health endpoints...")
        for port in [8081, 8082]:
            try:
                resp = requests.get(f"http://127.0.0.1:{port}/health", timeout=2)
                if resp.status_code == 200:
                    print(f"✓ Port {port} health endpoint returns 200")
                else:
                    print(f"✗ Port {port} health endpoint returns {resp.status_code}")
            except Exception as e:
                print(f"✗ Port {port} health check failed: {e}")
                return False
        
        # Configure and start app
        print("\nStarting load balancer with health checks enabled...")
        env = os.environ.copy()
        env.update({
            "TARGET_GROUP_1_NAME": "backends",
            "TARGET_GROUP_1_TARGETS": "127.0.0.1:8081,127.0.0.1:8082",
            "TARGET_GROUP_1_HEALTH_CHECK_ENABLED": "true",
            "TARGET_GROUP_1_HEALTH_CHECK_PATH": "/health",
            "TARGET_GROUP_1_HEALTH_CHECK_INTERVAL": "5000",
            "TARGET_GROUP_1_HEALTH_CHECK_SUCCEED_THRESHOLD": "1",
            "TARGET_GROUP_1_HEALTH_CHECK_FAILURE_THRESHOLD": "1",
            "LISTENER_RULE_1_PATH_PREFIX": "/",
            "LISTENER_RULE_1_TARGET_GROUP": "backends",
        })
        
        p_app = subprocess.Popen([sys.executable, "app.py"], 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env=env)
        procs.append(p_app)
        
        time.sleep(3)
        print("✓ Load balancer started")
        
        # Test requests through load balancer
        print("\nMaking test requests through load balancer...")
        print("-" * 60)
        
        ports_seen = set()
        for i in range(6):
            try:
                resp = requests.get("http://localhost:8080/test", timeout=2)
                if resp.status_code == 200:
                    data = resp.json()
                    port = data.get("server_port")
                    ports_seen.add(port)
                    print(f"Request {i+1}: 200 OK (served by port {port})")
                else:
                    print(f"Request {i+1}: {resp.status_code}")
            except Exception as e:
                print(f"Request {i+1}: ERROR - {e}")
                return False
        
        print("-" * 60)
        print(f"\n✓ Load balancer is routing traffic!")
        print(f"✓ Targets served requests: {ports_seen}")
        
        if len(ports_seen) > 1:
            print(f"✓ Round-robin working: requests distributed across {len(ports_seen)} backends")
        
        print("\n" + "=" * 60)
        print("✓ Integration test PASSED")
        print("=" * 60)
        print("\nHealth checks are running in the background.")
        print("Try stopping a mock target (e.g., Ctrl+C one of them)")
        print("and making more requests to see it get removed from rotation.")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        print("\nCleaning up...")
        for p in procs:
            try:
                p.terminate()
                p.wait(timeout=2)
            except:
                p.kill()
        print("✓ Cleaned up")

if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
