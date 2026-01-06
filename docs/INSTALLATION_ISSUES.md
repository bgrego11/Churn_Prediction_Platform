# Fresh Installation Issues & Fixes

## Summary
When cloning this repository to a brand new host, several setup steps are **missing from documentation** or **require manual action**. This guide identifies gaps and provides solutions.

---

## 🔴 Critical Issues (Blocking Fresh Install)

### Issue 1: Hard-Coded Paths in `.env`
**Problem:** `.env` file contains absolute paths specific to original developer's machine:
```dotenv
AIRFLOW_HOME=/Users/ben/Churn_Prediction_Platform/airflow
AIRFLOW__CORE__DAGS_FOLDER=/Users/ben/Churn_Prediction_Platform/airflow_dags
OFFLINE_FEATURE_STORE_PATH=/Users/ben/Churn_Prediction_Platform/data/features
MODEL_ARTIFACT_PATH=/Users/ben/Churn_Prediction_Platform/data/models
RAW_DATA_PATH=/Users/ben/Churn_Prediction_Platform/data/raw
LOGS_PATH=/Users/ben/Churn_Prediction_Platform/data/logs
```

**Impact:** Fresh clone will fail when run on different host (e.g., `/Users/alice/...` or `/home/user/...`)

**Fix:** 
```bash
# After cloning, create setup script to update paths:
PROJECT_DIR=$(pwd)
sed -i.bak "s|/Users/ben/Churn_Prediction_Platform|$PROJECT_DIR|g" .env

# Or update manually:
export PROJECT_DIR=/path/to/Churn_Prediction_Platform
# Then edit .env to replace all /Users/ben/... with $PROJECT_DIR
```

**Better Fix (for repository):** 
Use relative paths or environment variable substitution in `.env`:
```dotenv
# Change from absolute to relative:
AIRFLOW_HOME=./airflow
AIRFLOW__CORE__DAGS_FOLDER=./airflow_dags
OFFLINE_FEATURE_STORE_PATH=./data/features
MODEL_ARTIFACT_PATH=./data/models
RAW_DATA_PATH=./data/raw
LOGS_PATH=./data/logs
```

---

### Issue 2: Required Directories Don't Exist on Fresh Clone
**Problem:** Docker Compose references bind mounts that don't exist:
```yaml
# docker-compose.yml
volumes:
  - ./data:/app/data           # ./data MUST EXIST locally
  - ./airflow:/app/airflow_home # ./airflow MUST EXIST locally
```

**Impact:** First `docker-compose up` will fail with permission errors or create directories with wrong permissions.

**Missing From Docs:**
- [ ] Step to create `./data` directory
- [ ] Step to create `./data/models` subdirectory (for model persistence)
- [ ] Step to create `./data/features` subdirectory (for offline feature store)
- [ ] Step to create `./airflow` directory
- [ ] Step to create `./airflow/logs` subdirectory (for DAG execution logs)

**Current Docs:** README says `docker-compose up -d` but doesn't mention these prerequisites.

**Fix:** Add to README Getting Started section:
```bash
# Create required directories before docker-compose up
mkdir -p data/models data/features data/raw data/logs
mkdir -p airflow/logs
```

---

### Issue 3: REDIS_HOST Hardcoded to localhost
**Problem:** `.env` sets:
```dotenv
REDIS_HOST=localhost
```

**Issue:** When running inside Docker containers (Airflow, FastAPI), they can't reach `localhost:6379`. Must use `redis` (Docker service name).

**Fix:** Change in `.env`:
```dotenv
# For Docker environment (default):
REDIS_HOST=redis

# For local testing only:
# REDIS_HOST=localhost
```

---

## 🟡 Moderate Issues (Likely to Cause Confusion)

### Issue 4: README "Getting Started" is Too Minimal
**Current docs:**
1. Start services: `docker-compose up -d`
2. Verify: `docker-compose ps`
3. Make prediction: `curl http://localhost:8000/predict/1`

**Missing from docs:**
- [ ] No mention of directory creation prerequisites
- [ ] No wait time documented (Postgres takes 10-15 seconds to initialize)
- [ ] No data loading step (fresh clone has empty database)
- [ ] No mention that predictions will fail if no model exists
- [ ] No troubleshooting guide for common failures

**Fix:** See `docs/FRESH_INSTALLATION.md` (already created above)

---

### Issue 5: No `.env.example` Template for New Developers
**Problem:** `.env` is in repo with hardcoded paths. New developers might:
- Copy it as-is without updating paths
- Commit secrets to repo
- Not understand which values are required vs optional

**Current approach:** `.env` is checked in with full config + hardcoded paths

**Better approach:** 
- Create `.env.example` with templated values
- Add `.env` to `.gitignore`
- Users copy and customize `.env` from template

**Fix:**
```bash
# Create .env.example (template)
cp .env .env.example

# Edit .env.example to use placeholders:
AIRFLOW_HOME=/path/to/Churn_Prediction_Platform/airflow
AIRFLOW__CORE__DAGS_FOLDER=/path/to/Churn_Prediction_Platform/airflow_dags
# etc.

# Then add to .gitignore:
echo ".env" >> .gitignore
```

---

### Issue 6: Airflow UI Not Mentioned in Setup Docs
**Problem:** README only mentions FastAPI at `http://localhost:8000`. 

**Missing:** Airflow UI at `http://localhost:8080` with default credentials `admin/airflow`

**Fix:** Add to README:
```bash
# Access Airflow UI
http://localhost:8080
Login: admin / airflow

# View DAGs
airflow dags list

# Trigger DAG
airflow dags trigger churn_platform_main
```

---

## 🟢 Minor Issues (Documentation Gaps)

### Issue 7: Data Loading Step Not Documented
**Problem:** Fresh clone has empty database. Predictions fail because:
1. No data in `raw_data.users`
2. No data in `raw_data.user_events`
3. No trained model in `data/models/churn_model.pkl`

**Missing from docs:**
- [ ] How to generate synthetic data
- [ ] How to load sample data
- [ ] How to train initial model

**Current workaround (not documented):**
```bash
# Option 1: Trigger DAG (will fail if no data exists)
docker-compose exec airflow-webserver airflow dags trigger churn_platform_main

# Option 2: Run data generation test
docker-compose exec airflow-webserver python tests/phase2/test_data_generation.py

# Option 3: Run training directly
docker-compose exec airflow-webserver python tests/phase4/test_model_training.py
```

---

### Issue 8: Model Persistence Not Documented
**Problem:** Users might not understand that models persist to `./data/models` via Docker volume.

**Missing from docs:**
- [ ] Explanation of `./data/models` directory
- [ ] How model gets loaded on startup
- [ ] Where to find trained model file

---

### Issue 9: Batch Feature Optimization Not Documented
**Problem:** Recent optimization to batch SQL queries is in code but not in ANY documentation.

**Missing from docs:**
- [ ] Architecture docs explaining batch feature pipeline
- [ ] Performance improvement numbers (50-100x faster)
- [ ] Explanation of window functions and batch query design
- [ ] Troubleshooting guide if feature computation fails

---

## ✅ Complete Checklist for Fresh Installation

When cloning to new host, user must:

```bash
# 1. Clone repository
git clone <repo> Churn_Prediction_Platform
cd Churn_Prediction_Platform

# 2. Update .env paths (CRITICAL)
PROJECT_DIR=$(pwd)
sed -i.bak "s|/Users/ben/Churn_Prediction_Platform|$PROJECT_DIR|g" .env

# 3. Create required directories (CRITICAL)
mkdir -p data/models data/features data/raw data/logs
mkdir -p airflow/logs

# 4. Fix REDIS_HOST in .env
sed -i.bak 's/REDIS_HOST=localhost/REDIS_HOST=redis/g' .env

# 5. Start services
docker-compose up -d

# 6. Wait for services to initialize (15-20 seconds)
sleep 20

# 7. Verify services running
docker-compose ps

# 8. Load initial data
docker-compose exec airflow-webserver python tests/phase2/test_data_generation.py

# 9. Train initial model
docker-compose exec airflow-webserver python tests/phase4/test_model_training.py

# 10. Test prediction
curl http://localhost:8000/predict/1
```

---

## Recommendations for Repository

### Priority 1 (Fix Immediately)
- [ ] Change `.env` to use relative paths instead of `/Users/ben/...`
- [ ] Add directory creation step to README
- [ ] Create `.env.example` and add `.env` to `.gitignore`

### Priority 2 (Add Documentation)
- [ ] Create `docs/FRESH_INSTALLATION.md` with complete setup steps ✅ *Done*
- [ ] Update README "Getting Started" with directory creation
- [ ] Document Airflow UI access and DAG triggering
- [ ] Document data loading step

### Priority 3 (Enhancement)
- [ ] Create automated setup script (`./scripts/setup.sh`)
- [ ] Document batch feature optimization in architecture guide
- [ ] Add troubleshooting section to README

---

## Quick Fix Script

Here's a one-line fix for path issues on fresh clone:

```bash
# Run this immediately after cloning:
PROJECT_DIR=$(pwd) && sed -i.bak "s|/Users/ben/Churn_Prediction_Platform|$PROJECT_DIR|g" .env && sed -i.bak 's/REDIS_HOST=localhost/REDIS_HOST=redis/g' .env && mkdir -p data/{models,features,raw,logs} airflow/logs && echo "✓ Setup complete!"
```

Or as a script:

```bash
#!/bin/bash
set -e

PROJECT_DIR=$(pwd)
echo "📁 Project directory: $PROJECT_DIR"

# Update .env paths
echo "🔧 Updating .env paths..."
sed -i.bak "s|/Users/ben/Churn_Prediction_Platform|$PROJECT_DIR|g" .env
sed -i.bak 's/REDIS_HOST=localhost/REDIS_HOST=redis/g' .env

# Create directories
echo "📂 Creating required directories..."
mkdir -p data/{models,features,raw,logs}
mkdir -p airflow/logs

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  docker-compose up -d"
echo "  sleep 20"
echo "  docker-compose ps"
```

---

## Validation After Fresh Clone

Run these commands to validate setup:

```bash
# 1. Check .env paths updated
grep "PROJECT_DIR_HERE\|/Users/ben" .env  # Should be EMPTY

# 2. Check directories exist
ls -la data/models data/features airflow/logs

# 3. Check containers running
docker-compose ps  # All should show "Up"

# 4. Check Postgres initialization
docker-compose exec postgres psql -U churn_user -d churn_db -c "SELECT COUNT(*) FROM raw_data.users;"

# 5. Check Redis connectivity
docker-compose exec redis redis-cli ping  # Should return "PONG"

# 6. Check FastAPI health
curl http://localhost:8000/health

# 7. Check Airflow DAG loaded
docker-compose exec airflow-webserver airflow dags list | grep churn_platform_main
```
