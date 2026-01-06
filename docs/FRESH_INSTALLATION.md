# Setup Guide: Fresh Installation on New Host

This guide documents all steps needed to clone and run the Churn Prediction Platform on a brand new machine.

---

## Prerequisites

Before starting, ensure you have:
- **Git** (for cloning)
- **Docker** (version 20.10+)
- **Docker Compose** (version 1.29+)
- **Make** (optional, but recommended)
- **Python 3.10+** (for local development, optional)

```bash
# Verify installations
docker --version
docker-compose --version
make --version
python3 --version
```

---

## Step 1: Clone Repository

```bash
git clone <repository-url> Churn_Prediction_Platform
cd Churn_Prediction_Platform
```

---

## Step 2: Verify Required Directories

Your project already has the `./data` directory with the trained model. Verify it exists:

```bash
# Check data directory
ls -la data/

# Expected output:
# models/           (contains trained models)
# features/         (created by platform when caching features)
# logs/             (created by platform when needed)
```

**About directories in this project:**
- `data/` - Bind-mounted to containers as `/app/data`
- `data/models/` - Already exists (contains your trained models)
- `data/features/` - Created automatically when platform caches features
- `airflow/logs/` - Docker-managed named volume (created automatically)
- `postgres_data/` - Docker-managed named volume (created automatically)
- `redis_data/` - Docker-managed named volume (created automatically)

**Important:** You DON'T need to pre-create `airflow/logs/`, `postgres_data/`, or `redis_data/`. Docker automatically creates and manages these named volumes.

---

## Step 3: Update Environment File for Your Machine

The `.env` file exists but has hard-coded paths from the original developer's machine (`/Users/ben/...`). **You must update these:**

```bash
# Check .env exists and has hard-coded paths
cat .env | grep "Users/ben"

# If you see paths like "/Users/ben/Churn_Prediction_Platform", update them:
PROJECT_DIR=$(pwd)
sed -i.bak "s|/Users/ben/Churn_Prediction_Platform|$PROJECT_DIR|g" .env

# Verify REDIS_HOST is set correctly for Docker (not localhost):
grep REDIS_HOST .env
# Should show: REDIS_HOST=redis (not localhost)
```

**Key variables to verify:**
- `POSTGRES_HOST=postgres` (Docker service name)
- `REDIS_HOST=redis` (Docker service name, NOT localhost)
- `AIRFLOW__CORE__DAGS_FOLDER` points to your actual `airflow_dags` directory
- `MODEL_ARTIFACT_PATH` points to your actual `data/models` directory

**For production deployments:**
- Change `ENV=development` to `ENV=production`
- Change `DEBUG=true` to `DEBUG=false`
- Update `POSTGRES_PASSWORD` to a strong value
- Use secrets manager instead of `.env` for credentials

---

## Step 4: Start Docker Services

```bash
# Start all containers in background
docker-compose up -d

# Docker will automatically create named volumes:
# - postgres_data (PostgreSQL persistence)
# - redis_data (Redis persistence)  
# - airflow_logs (Airflow execution logs)

# Wait for services to initialize (PostgreSQL takes 10-15 seconds)
sleep 20

# Verify all containers are running
docker-compose ps

# Expected output:
# - churn-postgres: Up (Healthy)
# - churn-redis: Up (Healthy)
# - churn-fastapi: Up
# - airflow-init: Exited 0 (initialization complete)
# - airflow-webserver: Up
# - airflow-scheduler: Up
```

---

## Step 5: Initialize Airflow Database

Airflow needs its metadata database initialized. This happens automatically via the `airflow-init` container, but verify:

```bash
# Check if Airflow DB is ready
docker-compose exec -T postgres psql -U churn_user -d airflow_db -c "SELECT version();"

# If error, manually initialize (should not be needed):
docker-compose exec airflow-init airflow db init
```

---

## Step 6: Verify Database Initialization

PostgreSQL will auto-initialize with the provided SQL scripts. Verify tables exist:

```bash
# Connect to database
docker-compose exec postgres psql -U churn_user -d churn_db

# Inside psql:
\dt raw_data.*           -- Check raw data tables
\dt ml_pipeline.*        -- Check ML pipeline tables
\q                       -- Exit psql
```

**Expected tables:**
- `raw_data.users` - User profiles
- `raw_data.user_events` - Event log
- `raw_data.billing_events` - Payment transactions
- `ml_pipeline.features` - Computed feature vectors
- `ml_pipeline.labels` - Churn labels (for training)
- `ml_pipeline.models` - Model metadata
- `ml_pipeline.predictions` - Prediction cache

---

## Step 7: Verify API is Running

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy"}

# Test prediction endpoint
curl http://localhost:8000/predict/1

# Should return prediction for user 1
```

---

## Step 8: Verify Airflow DAG Setup

```bash
# Check DAGs are detected
docker-compose exec airflow-webserver airflow dags list

# Expected: churn_platform_main should be listed

# View DAG details
docker-compose exec airflow-webserver airflow dags info churn_platform_main
```

---

## Step 9: Load Initial Data (Optional but Recommended)

By default, no data is loaded. To populate the database with synthetic data:

```bash
# Option A: Run data generation test
docker-compose exec airflow-webserver python tests/phase2/test_data_generation.py

# Option B: Trigger DAG manually
docker-compose exec airflow-webserver airflow dags test churn_platform_main 2026-01-06

# This will:
# 1. Generate 10,000 synthetic users
# 2. Create events and billing transactions
# 3. Compute features for all users
# 4. Cache features in Redis
```

---

## Step 10: Verify Everything Works

Run the comprehensive test suite:

```bash
# Run all tests
make test

# Or test individual components:
make test-phase2   # Data generation
make test-phase3   # Feature engineering
make test-phase4   # Model training
make test-phase5   # Predictions
make test-phase6   # Monitoring
make test-phase7   # A/B testing
```

---

## Missing Files/Steps Not in Documentation

### ✅ **Now Documented:**
1. **Directory Creation** - `data/models`, `data/features`, `airflow/logs` (critical for persistence)
2. **.env File** - Already in repo, but should verify paths
3. **Volume Mounts** - Docker-compose handles these, but understand what persists
4. **Airflow DB Init** - Happens automatically, but may need manual verification
5. **Initial Data Load** - No data by default, needs synthetic generation
6. **Environment Variables** - AIRFLOW paths are hardcoded to specific user path

### ⚠️ **Important Notes:**

**For Production on New Host:**
1. Update `.env` paths from `/Users/ben/...` to your actual paths
2. Create `.env.prod` with production credentials
3. Use Docker secrets instead of plain text passwords
4. Set up persistent volumes on production storage
5. Configure backup schedules for `data/` directories

**Docker Data Persistence:**
- Named volumes (`postgres_data`, `redis_data`, `airflow_logs`) persist automatically
- Bind mounts (`./data:/app/data`) need directories to exist locally
- Models must be saved to `./data/models` (mounted) to survive restarts

**Airflow Setup:**
- `airflow_logs` is a Docker-managed named volume (created automatically)
- DAG folder path in `.env` must match your actual `airflow_dags` location
- First startup creates Airflow metadata DB automatically
- Webserver UI available at http://localhost:8080

---

## Checklist for Fresh Installation

```bash
☐ Clone repository
☐ Verify data/ directory exists (should already be there)
☐ Update .env paths from /Users/ben/... to your actual directory
☐ Fix REDIS_HOST=redis if it says localhost
☐ docker-compose up -d
☐ Wait 20 seconds for services to start
☐ Verify all containers running: docker-compose ps
☐ Test API: curl http://localhost:8000/health
☐ Generate initial data: docker-compose exec airflow-webserver python tests/phase2/test_data_generation.py
☐ Train model: docker-compose exec airflow-webserver python tests/phase4/test_model_training.py
☐ Make prediction: curl http://localhost:8000/predict/1
☐ Access Airflow UI: http://localhost:8080 (admin/admin)
```

---

## Troubleshooting Fresh Installation

### Postgres Connection Failed
```bash
# Wait longer for postgres to start
docker-compose logs postgres | grep "ready to accept"
# If not ready, restart:
docker-compose restart postgres
```

### Airflow DAG Not Visible
```bash
# Verify DAG folder exists and is mounted
docker-compose exec airflow-webserver ls /opt/airflow/dags
# Should show: churn_platform_main.py
```

### Models Directory Missing
```bash
# Create and ensure ownership
mkdir -p data/models
chmod 777 data/models
# Restart containers
docker-compose restart
```

### FastAPI Returns 500 Error
```bash
# Check if model file exists
ls -la data/models/churn_model.pkl
# If missing, run test-phase4 to train model
make test-phase4
```

---

## Next Steps After Setup

1. **Run a prediction:**
   ```bash
   curl http://localhost:8000/predict/1
   ```

2. **Monitor Airflow DAG:**
   - Visit http://localhost:8080
   - Default login: admin/airflow

3. **Check model performance:**
   ```bash
   docker-compose exec airflow-webserver python -c "
   from src.models.model_trainer import ModelTrainer
   trainer = ModelTrainer(host='postgres', user='churn_user', password='churn_password')
   trainer.connect()
   # View model metrics
   "
   ```

4. **Deploy to production:** See [Deployment Guide](../docs/DEPLOYMENT.md)

---

## Cleanup Commands

If you need to start fresh:

```bash
# Stop all services
docker-compose down

# Remove all data (⚠️ destructive)
rm -rf data/models/* data/features/* data/logs/*

# Clean Docker resources
docker-compose down -v  # Remove named volumes
rm -rf airflow/logs/*   # Remove Airflow logs

# Restart clean
docker-compose up -d
```
