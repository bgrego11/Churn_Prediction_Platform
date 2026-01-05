# Implementation Plan & Roadmap

## Phase Breakdown

### Phase 1: ✅ COMPLETE - Project Foundation

**Completed:**
- ✅ Directory structure created
- ✅ requirements.txt with conflict-resolved versions
- ✅ .env.example configuration template
- ✅ docker-compose.yml (Postgres + Redis + Airflow + FastAPI)
- ✅ Dockerfile for FastAPI service
- ✅ Makefile with 15+ automation commands
- ✅ Airflow DAG structure (churn_platform_main.py)
- ✅ Core utilities (config.py, db_manager.py)
- ✅ README.md with full architecture diagram
- ✅ TECH_STACK.md with dependency conflict resolution

**Output:** Complete scaffolding ready for implementation

---

## Phase 2: Synthetic Data Generation

**Status:** Ready to implement  
**Priority:** HIGH (blocks all downstream phases)

### What to build:
```
src/data_generation/
├── generator.py           # Main SyntheticDataGenerator class
├── schemas.py            # Data schemas (Pydantic models)
└── events.py             # Event generators
```

### Key features:
- Deterministic generation (seeded with SYNTHETIC_DATA_SEED=42)
- Three tables: users, user_events, billing_events
- Backfill capability (generate 12 months of historical data)
- Daily incremental generation
- Support for late-arriving events
- Insert directly to Postgres raw_data schema

### Entry point:
```bash
python -m src.data_generation.generator
# or via Airflow: task 1 of churn_platform_main DAG
```

---

## Phase 3: Raw Data Storage Layer

**Status:** Ready to implement  
**Priority:** HIGH (needed after Phase 2)

### What's already done:
- ✅ Postgres Docker container (postgres:15-alpine)
- ✅ Database initialization script (docker/postgres_init.sql)
- ✅ Schema definition (users, user_events, billing_events tables)
- ✅ Indexes for performance (user_id, event_time)

### What to build:
```
src/data_generation/
├── loaders.py            # Insert data into Postgres
└── validators.py         # Data quality checks
```

### Key features:
- Bulk insert from generator to Postgres
- Data validation (schema checks, timestamp ordering)
- Foreign key integrity (user_id references)
- Optional export to Parquet

---

## Phase 4: Batch Feature Pipeline (⭐ CRITICAL)

**Status:** Ready to implement  
**Priority:** CRITICAL (core ML component)

### What to build:
```
src/features/
├── batch_feature_pipeline.py  # Main feature computation
├── feature_definitions.py     # Feature specs
└── pit_validator.py          # PIT correctness checks
```

### Features to implement:
```python
avg_sessions_7d          # avg daily sessions in 7d window
sessions_30d             # count distinct sessions in 30d
days_since_last_login    # max days since last login event
failed_payments_30d      # count failed charges in 30d
total_spend_90d          # sum amount of successful charges in 90d
is_pro_plan              # from users table (static)
label_churned_30d        # (training only) churned in next 30d?
```

### ⚠️ CRITICAL REQUIREMENT: Point-in-Time Correctness
```python
def compute_features(user_id, feature_time):
    # RULE 1: Only use events where event_time <= feature_time
    # RULE 2: Labels only from events in (feature_time, feature_time + 30d]
    # RULE 3: Results must be reproducible for any historical timestamp
```

### Tests required:
- PIT correctness validation
- Feature leakage detection
- Reproducibility (same seed = same results)

---

## Phase 5: Offline Feature Store

**Status:** Ready to implement  
**Priority:** HIGH (needed for training)

### What to build:
```
src/stores/
└── offline_store.py      # Parquet-based feature store
```

### Implementation:
- Partition Parquet files by feature_time (year/month/day)
- Store full history (all users × all feature_times)
- Include labels for training
- Query interface for fetching features by user + time

### Storage location:
```
data/features/
├── year=2024/month=01/day=01.parquet
├── year=2024/month=01/day=02.parquet
└── ...
```

---

## Phase 6: Online Feature Store

**Status:** Ready to implement  
**Priority:** HIGH (needed for inference)

### What to build:
```
src/stores/
└── online_store.py       # Redis-based feature store
```

### Implementation:
- Store latest feature vector per user in Redis
- Key format: `user_features:{user_id}`
- Value: JSON with features + feature_time
- Daily sync job (push latest from offline to online)
- Health check endpoint

### SLA:
- Latency: < 100ms per lookup
- Availability: 99.9% (handled by Redis)

---

## Phase 7: Model Training & Registry

**Status:** Ready to implement  
**Priority:** HIGH (needed for inference)

### What to build:
```
src/models/
├── training.py          # ModelTrainer class
└── registry.py          # Model artifact versioning
```

### Implementation:
- LogisticRegression from scikit-learn
- No hyperparameter tuning
- Train on last 6 months of data
- Save model.joblib + metadata.json
- Auto-increment version (v001, v002, ...)

### Storage:
```
data/models/churn_model/
├── v001/
│   ├── model.joblib
│   ├── metadata.json      # training_time, feature_schema_hash, etc.
│   └── training_data_sample.parquet
├── v002/
└── ...
```

---

## Phase 8: FastAPI Prediction Service

**Status:** Ready to implement  
**Priority:** HIGH (public interface)

### What to build:
```
src/inference/
├── api.py               # FastAPI application
├── models.py            # Request/response Pydantic models
└── predictor.py         # Inference logic
```

### Endpoints:
```
POST /predict
  Input:  { "user_id": "user_123" }
  Output: {
    "churn_probability": 0.34,
    "model_version": "v001",
    "feature_time": "2025-01-05T00:00:00Z",
    "features": {...}
  }

GET /health
GET /model/version
```

### Requirements:
- Fetch features from Redis (< 50ms)
- Load model from disk (cached)
- Run inference (< 20ms)
- Log prediction (async)
- Return in < 100ms total

---

## Phase 9: Monitoring & Drift Detection

**Status:** Ready to implement  
**Priority:** MEDIUM (observability)

### What to build:
```
src/monitoring/
├── drift_detection.py   # Drift detection logic
├── logger.py           # Prediction logging
└── metrics.py          # Monitoring metrics
```

### Drift checks:
1. **Feature Drift**
   - PSI (Population Stability Index)
   - Threshold: PSI > 0.1 = alert
   - Z-score test per feature
   - Threshold: |z| > 3σ = alert

2. **Prediction Drift**
   - Mean churn probability shift
   - Distribution changes

3. **Schema Drift**
   - Missing features
   - NaN patterns

### Output:
- drift_logs.parquet (daily)
- Alerts logged to logs/

---

## Phase 10: Airflow DAGs

**Status:** Partially complete (skeleton exists)  
**Priority:** MEDIUM (orchestration)

### What's done:
- ✅ Main DAG structure (churn_platform_main.py)
- ✅ Task dependencies defined
- ✅ Scheduling (daily 1 AM UTC)

### What to complete:
- Implement task callables with full logic
- Add error handling + retries
- Add SLAs (service level agreements)
- Test each task in isolation

### DAG flow:
```
generate_data
    ↓
compute_features
    ↓
sync_online_features
    ├→ train_model (Mon-Wed)
    └→ run_drift_detection
            ↓
        validate_schema
```

---

## Phase 11: Testing

**Status:** Ready to implement  
**Priority:** HIGH (prevents bugs)

### Test categories:

1. **PIT Correctness Tests** (CRITICAL)
   ```python
   # Verify features at time T only use events ≤ T
   # Verify labels only use events in (T, T+30d]
   ```

2. **Feature Leakage Tests**
   ```python
   # Ensure no forward-looking features
   # Check computed features against whitelist
   ```

3. **Schema Validation Tests**
   ```python
   # Feature columns match model input
   # No NaN in critical features
   ```

4. **API Contract Tests**
   ```python
   # POST /predict returns correct schema
   # GET /health returns 200
   ```

5. **Reproducibility Tests**
   ```python
   # Same seed = same data
   # Same features = same predictions
   ```

### Test files:
```
tests/
├── test_pit_correctness.py
├── test_feature_leakage.py
├── test_schema_validation.py
├── test_api_contracts.py
└── test_reproducibility.py
```

---

## Phase 12: Docker & Local Deployment

**Status:** Partially complete (docker-compose.yml done)  
**Priority:** MEDIUM (environment management)

### What's done:
- ✅ docker-compose.yml with all services
- ✅ Dockerfile for FastAPI
- ✅ PostgreSQL init script
- ✅ Makefile commands

### What to verify:
- Docker Compose starts all 6 services
- Postgres initializes correctly
- Redis connects without issues
- Airflow webui accessible
- FastAPI starts and serves requests
- Health checks pass

### One-command setup:
```bash
make setup        # Install deps + env
make docker-up    # Start all services
```

---

## Phase 13: Documentation

**Status:** Mostly complete  
**Priority:** LOW (reference material)

### What's done:
- ✅ README.md (60+ lines with architecture)
- ✅ TECH_STACK.md (versioning + conflicts)
- ✅ This roadmap

### What to add (if time permits):
- Feature definitions (docs/FEATURES.md)
- API reference (docs/API.md)
- Design decisions (docs/DESIGN.md)
- Known limitations (docs/LIMITATIONS.md)
- Future improvements (docs/FUTURE.md)

---

## Implementation Order (Recommended)

**Week 1:**
1. Phase 2: Synthetic Data Generator
2. Phase 3: Raw Data Storage (loaders + validators)
3. Phase 4: Batch Feature Pipeline (CRITICAL)

**Week 2:**
4. Phase 5: Offline Feature Store
5. Phase 6: Online Feature Store
6. Phase 7: Model Training & Registry

**Week 3:**
7. Phase 8: FastAPI Prediction Service
8. Phase 9: Monitoring & Drift Detection
9. Phase 11: Testing (comprehensive)

**Week 4:**
10. Phase 10: Airflow DAGs (complete)
11. Phase 12: Docker (verify + fix)
12. Phase 13: Documentation (polish)

---

## Success Metrics

By end of implementation:

✅ **Data Integrity:**
- Point-in-time correctness tests passing
- No feature leakage detected
- Schema validation 100%

✅ **Functionality:**
- All 7 features computed correctly
- Model trains weekly, auto-versioned
- API responds < 100ms
- Drift detection operational

✅ **Deployment:**
- `make docker-up` brings entire system online
- All health checks pass
- Airflow DAG runs successfully daily

✅ **Testing:**
- 40+ tests, all passing
- Test coverage > 80%
- CI/CD ready

✅ **Documentation:**
- README explains architecture
- API documented
- Tech stack decisions explained

---

## Dependency Notes (from Phase 1)

All versions are carefully pinned to avoid conflicts:

```
Apache Airflow 2.7.3         → SQLAlchemy 2.0.23
Pandas 2.1.3                 → NumPy 1.26.2
scikit-learn 1.3.2           → joblib 1.3.2
FastAPI 0.104.1              → Pydantic 2.5.0
PostgreSQL 15                → psycopg2-binary 2.9.9
Redis 7                      → redis-py 5.0.1
```

**No conflicts when using pinned versions.** ✅

---

## Questions? Next Steps?

1. **Start Phase 2?** → Synthetic data generator
2. **Need clarification?** → Check TECH_STACK.md
3. **Want architecture changes?** → Discuss before Phase 2

**Estimated total implementation time:** 3-4 weeks for complete system
