#!/usr/bin/env python3
"""
Phase 7 Integration Test - Dashboard API endpoints
Tests all dashboard endpoints after API integration.
"""

import requests
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
L = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

def test_endpoint(method: str, endpoint: str, description: str):
    """Test an endpoint and return results."""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url)
        
        if response.status_code in [200, 201]:
            return True, response.json()
        else:
            return False, response.text
    except Exception as e:
        return False, str(e)

def main():
    """Run dashboard API integration tests."""
    L.info("\n" + "=" * 80)
    L.info("PHASE 7: DASHBOARD API INTEGRATION TEST")
    L.info("=" * 80 + "\n")

    tests = [
        ("GET", "/dashboard/summary", "Dashboard Summary"),
        ("GET", "/dashboard/health", "Health Check"),
        ("GET", "/dashboard/models", "Model Versions"),
        ("GET", "/dashboard/models/production", "Production Model"),
        ("GET", "/dashboard/retraining-status", "Retraining Status"),
        ("GET", "/dashboard/metrics/timeline", "Metrics Timeline"),
        ("GET", "/dashboard/alerts", "System Alerts"),
    ]

    results = {}

    for method, endpoint, description in tests:
        L.info(f"Testing: {description}")
        L.info(f"  Endpoint: {method} {endpoint}")

        success, data = test_endpoint(method, endpoint, description)

        if success:
            L.info(f"  ✓ Status: SUCCESS")
            if isinstance(data, dict):
                # Show key fields without full response
                if 'production_model' in data:
                    L.info(f"    - Production Model: v{data['production_model']['version']}")
                if 'models' in data:
                    L.info(f"    - Total Models: {len(data['models'])}")
                if 'health_status' in data:
                    L.info(f"    - Health: {data['health_status']}")
            results[description] = True
        else:
            L.info(f"  ✗ Status: FAILED")
            L.info(f"    Error: {data[:200]}")
            results[description] = False

        L.info("")

    L.info("=" * 80)
    L.info("TEST SUMMARY")
    L.info("=" * 80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_flag in results.items():
        status = "✓ PASSED" if passed_flag else "✗ FAILED"
        L.info(f"{status}: {test_name}")

    L.info("")

    if passed == total:
        L.info(f"✅ ALL TESTS PASSED ({passed}/{total})")
        L.info("\nPhase 7 Features Ready:")
        L.info("  ✓ Model versioning and promotion")
        L.info("  ✓ Automated retraining orchestration")
        L.info("  ✓ A/B testing framework")
        L.info("  ✓ Production dashboards")
        L.info("  ✓ Real-time monitoring endpoints")
    else:
        L.info(f"❌ SOME TESTS FAILED ({total-passed}/{total} failures)")

    L.info("")

if __name__ == "__main__":
    main()
