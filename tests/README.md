# Test Suite - Churn Prediction Platform

Organized testing directory for all development and validation tests.

## 📁 Directory Structure

```
tests/
├── phase1/                          Phase 1: Infrastructure (Docker)
├── phase2/                          Phase 2: Data Generation
│   └── test_data_generation.py
├── phase3/                          Phase 3: Feature Engineering
│   └── test_features.py
├── phase4/                          Phase 4: Model Training
│   └── test_models.py
├── phase5/                          Phase 5: Online Serving
│   └── test_serving.py
├── phase6/                          Phase 6: Monitoring
│   └── test_monitoring.py
├── phase7/                          Phase 7: Advanced Features
│   ├── __init__.py
│   ├── test_advanced.py             Unit tests for Phase 7 components
│   └── test_dashboard.py            Integration tests for Dashboard API
└── README.md                        This file
```

## 🧪 Phase Tests

### Phase 2: Data Generation
**File:** `phase2/test_data_generation.py`
- Tests synthetic data generation
- Validates event and billing data creation

**Run Test:**
```bash
python3 tests/phase2/test_data_generation.py
```

### Phase 3: Feature Engineering
**File:** `phase3/test_features.py`
- Tests feature pipeline
- Validates point-in-time correctness
- Checks feature aggregation

**Run Test:**
```bash
python3 tests/phase3/test_features.py
```

### Phase 4: Model Training
**File:** `phase4/test_models.py`
- Tests model training
- Validates model performance metrics
- Checks model persistence

**Run Test:**
```bash
python3 tests/phase4/test_models.py
```

### Phase 5: Online Serving
**File:** `phase5/test_serving.py`
- Tests online prediction serving
- Validates Redis caching
- Checks prediction latency

**Run Test:**
```bash
python3 tests/phase5/test_serving.py
```

### Phase 6: Monitoring
**File:** `phase6/test_monitoring.py`
- Tests prediction logging
- Validates drift detection
- Checks performance degradation monitoring

**Run Test:**
```bash
python3 tests/phase6/test_monitoring.py
```

### Phase 7: Advanced Features
**Files:** `phase7/test_advanced.py` & `phase7/test_dashboard.py`

#### test_advanced.py

**Test Coverage:**
- Model Registry: Version tracking, promotion workflow, history
- A/B Testing: Traffic splitting, variant assignment, statistical testing
- Retraining Orchestrator: Drift detection, validation, auto-promotion

**Run Test:**
```bash
docker exec churn-fastapi python3 /app/tests/phase7/test_advanced.py
```

**Expected Output:**
```
✓ PASSED: Model Registry
✓ PASSED: A/B Testing
✓ PASSED: Retraining Orchestrator

✅ PHASE 7 TEST SUCCESSFUL
```

### test_dashboard.py
**Purpose:** Integration testing of all Dashboard API endpoints

**Test Coverage:**
- /dashboard/summary
- /dashboard/health
- /dashboard/models
- /dashboard/models/production
- /dashboard/retraining-status
- /dashboard/metrics/timeline
- /dashboard/alerts

**Run Test:**
```bash
python3 tests/phase7/test_dashboard.py
```

**Expected Output:**
```
✅ ALL TESTS PASSED (7/7)

Phase 7 Features Ready:
  ✓ Model versioning and promotion
  ✓ Automated retraining orchestration
  ✓ A/B testing framework
  ✓ Production dashboards
  ✓ Real-time monitoring endpoints
```

## 🚀 Quick Test Commands

### Run All Phase Tests
```bash
# Phase 2: Data Generation
python3 tests/phase2/test_data_generation.py

# Phase 3: Feature Engineering
python3 tests/phase3/test_features.py

# Phase 4: Model Training
python3 tests/phase4/test_models.py

# Phase 5: Online Serving
python3 tests/phase5/test_serving.py

# Phase 6: Monitoring
python3 tests/phase6/test_monitoring.py

# Phase 7: Advanced Features (Unit)
docker exec churn-fastapi python3 /app/tests/phase7/test_advanced.py

# Phase 7: Advanced Features (Integration)
python3 tests/phase7/test_dashboard.py
```

### Run Specific Test Components
```python
# Test only Model Registry
docker exec churn-fastapi python3 << 'EOF'
from src.advanced.model_registry import ModelRegistry
# ... test code
EOF

# Test only A/B Testing
docker exec churn-fastapi python3 << 'EOF'
from src.advanced.ab_testing import ABTestManager
# ... test code
EOF
```

## 📊 Test Results Summary

### Latest Test Run
- **Date:** January 5, 2026
- **Phase 7 Unit Tests:** 3/3 PASSED ✅
- **Integration Tests:** 7/7 PASSED ✅
- **Overall Pass Rate:** 100%

### Component Test Status
| Component | Status | Notes |
|-----------|--------|-------|
| Model Registry | ✅ PASSED | Versioning and promotion working |
| A/B Testing | ✅ PASSED | Statistical significance validated |
| Retraining Orchestrator | ✅ PASSED | Drift detection functional |
| Dashboard API | ✅ PASSED | All 8 endpoints responding |

## 🔧 Test Configuration

### Database Setup
Tests use the same PostgreSQL database as production:
- Host: `postgres` (Docker) or `localhost` (local)
- Port: 5432
- Database: `churn_db`
- User: `churn_user`

### Environment Variables
```bash
export POSTGRES_HOST=postgres
export POSTGRES_PORT=5432
export POSTGRES_DB=churn_db
export POSTGRES_USER=churn_user
export POSTGRES_PASSWORD=churn_password
```

### Redis Configuration
```bash
export REDIS_HOST=redis
export REDIS_PORT=6379
export REDIS_DB=0
```

## 🔍 Manual Testing

### Test Model Registry
```python
from src.advanced.model_registry import ModelRegistry

registry = ModelRegistry(db_config)
registry.connect()

# Register a model
registry.register_model(
    model_name="churn_model",
    version="1.0",
    model_path="/tmp/model.pkl",
    scaler_path="/tmp/scaler.pkl",
    training_samples=1000,
    features=["feat1", "feat2"],
    hyperparameters={"C": 1.0},
    metrics={"auc": 0.95}
)

# Get production model
prod_model = registry.get_production_model()
print(prod_model)

registry.disconnect()
```

### Test A/B Testing
```python
from src.advanced.ab_testing import ABTestManager

ab_manager = ABTestManager(db_config)
ab_manager.connect()

# Start test
ab_manager.start_test(
    test_name="test_v2",
    control_version="1.0",
    variant_version="2.0",
    traffic_split=0.5
)

# Assign user
variant = ab_manager.assign_variant(user_id=1, test_name="test_v2")
print(f"User assigned to: {variant}")

ab_manager.disconnect()
```

### Test Dashboard Endpoints
```bash
# Get dashboard summary
curl http://localhost:8000/dashboard/summary

# Get health status
curl http://localhost:8000/dashboard/health

# Get model versions
curl http://localhost:8000/dashboard/models

# Get A/B test results
curl http://localhost:8000/dashboard/ab-tests/test_v2
```

## 📈 Adding New Tests

### Create Test File
```python
# tests/phase7/test_new_feature.py
import logging

logging.basicConfig(level=logging.INFO)
L = logging.getLogger(__name__)

def test_my_feature():
    """Test description."""
    L.info("\n[TEST] My Feature Test\n")
    
    # Test code here
    success = True
    
    if success:
        L.info("✅ TEST PASSED")
        return True
    else:
        L.info("❌ TEST FAILED")
        return False

if __name__ == "__main__":
    test_my_feature()
```

### Run New Test
```bash
python3 tests/phase7/test_new_feature.py
```

## 🐛 Debugging Tests

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Database State
```bash
docker exec -it churn-postgres psql -U churn_user -d churn_db

# View model versions
SELECT * FROM ml_pipeline.model_versions;

# View A/B tests
SELECT * FROM ml_pipeline.ab_tests;

# View predictions
SELECT * FROM ml_pipeline.ab_test_results LIMIT 10;
```

### Check Redis Cache
```bash
docker exec -it churn-redis redis-cli

# View cached features
KEYS feature:*
GET feature:user_1:features
```

### View API Logs
```bash
docker logs -f churn-fastapi
```

## ✅ Continuous Integration

### Pre-Commit Checklist
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Database schema is consistent
- [ ] No uncommitted changes

### CI/CD Pipeline (Future)
```bash
# Would run in CI/CD
pytest tests/
coverage report
black --check src/
mypy src/
```

## 📝 Test Documentation

For detailed test results and implementation details, see:
- [Phase 7 Complete Guide](../PHASE7_COMPLETE.md)
- [Quick Start Guide](../QUICK_START.md)
- Component README files in `src/advanced/`

## 🤝 Contributing

When adding new tests:
1. Follow existing test patterns
2. Include descriptive log messages
3. Test both success and failure cases
4. Clean up database state after tests
5. Update this README

---

**Last Updated:** January 5, 2026
**Status:** All tests passing ✅
