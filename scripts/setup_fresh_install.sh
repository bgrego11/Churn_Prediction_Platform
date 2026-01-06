#!/bin/bash
#
# Fresh Installation Setup Script
# Run this immediately after cloning the repository
#
# Usage: bash scripts/setup_fresh_install.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Churn Prediction Platform - Fresh Installation Setup         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo -e "${BLUE}→${NC} Project directory: ${GREEN}$PROJECT_DIR${NC}"
echo ""

# Step 1: Verify prerequisites
echo -e "${BLUE}[1/6]${NC} Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo -e "${RED}✗ Docker not found${NC}"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo -e "${RED}✗ Docker Compose not found${NC}"; exit 1; }
echo -e "${GREEN}✓${NC} Docker and Docker Compose installed"
echo ""

# Step 2: Update .env paths
echo -e "${BLUE}[2/6]${NC} Updating .env file paths..."
if [ -f "$PROJECT_DIR/.env" ]; then
    # Backup original
    cp "$PROJECT_DIR/.env" "$PROJECT_DIR/.env.backup"
    
    # Update paths using proper escaping
    sed -i.bak "s|/Users/ben/Churn_Prediction_Platform|$PROJECT_DIR|g" "$PROJECT_DIR/.env"
    
    # Fix REDIS_HOST for Docker
    if grep -q "REDIS_HOST=localhost" "$PROJECT_DIR/.env"; then
        sed -i.bak 's/REDIS_HOST=localhost/REDIS_HOST=redis/g' "$PROJECT_DIR/.env"
        echo -e "${GREEN}✓${NC} Updated REDIS_HOST to 'redis' (Docker service name)"
    fi
    
    echo -e "${GREEN}✓${NC} Updated paths in .env"
    echo -e "   Backup saved to: ${YELLOW}.env.backup${NC}"
else
    echo -e "${RED}✗ .env file not found${NC}"
    exit 1
fi
echo ""

# Step 3: Create directories
echo -e "${BLUE}[3/6]${NC} Creating required directories..."
mkdir -p "$PROJECT_DIR/data/models"
mkdir -p "$PROJECT_DIR/data/features"
mkdir -p "$PROJECT_DIR/data/raw"
mkdir -p "$PROJECT_DIR/data/logs"
mkdir -p "$PROJECT_DIR/airflow/logs"
mkdir -p "$PROJECT_DIR/airflow/plugins"

echo -e "${GREEN}✓${NC} Created data directories"
echo -e "   • data/models (model persistence)"
echo -e "   • data/features (offline feature store)"
echo -e "   • data/raw (raw data backups)"
echo -e "   • data/logs (platform logs)"
echo -e "${GREEN}✓${NC} Created airflow directories"
echo -e "   • airflow/logs (DAG execution logs)"
echo -e "   • airflow/plugins (custom plugins)"
echo ""

# Step 4: Start Docker services
echo -e "${BLUE}[4/6]${NC} Starting Docker services..."
cd "$PROJECT_DIR"
docker-compose up -d
echo -e "${GREEN}✓${NC} Services started"
echo ""

# Step 5: Wait for services to initialize
echo -e "${BLUE}[5/6]${NC} Waiting for services to initialize (20 seconds)..."
for i in {20..1}; do
    printf "\r   Waiting... ${YELLOW}%2d${NC} seconds remaining" $i
    sleep 1
done
printf "\r   Services ready!                        \n"
echo ""

# Step 6: Verify services
echo -e "${BLUE}[6/6]${NC} Verifying services..."
echo -e ""
echo "Container Status:"
docker-compose ps | tail -n +2 | while read line; do
    if echo "$line" | grep -q "Up"; then
        # Extract container name
        container=$(echo "$line" | awk '{print $1}')
        echo -e "  ${GREEN}✓${NC} $container"
    else
        echo -e "  ${RED}✗${NC} $line"
    fi
done
echo ""

# Quick health checks
echo "Service Health Checks:"

# Check FastAPI
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} FastAPI (http://localhost:8000)"
else
    echo -e "  ${YELLOW}⚠${NC} FastAPI not ready yet (will be ready shortly)"
fi

# Check PostgreSQL
if docker-compose exec -T postgres psql -U churn_user -d churn_db -c "SELECT 1" >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} PostgreSQL (churn_db)"
else
    echo -e "  ${RED}✗${NC} PostgreSQL not initialized"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Redis (cache store)"
else
    echo -e "  ${YELLOW}⚠${NC} Redis not responding yet"
fi

# Check Airflow DAG
if docker-compose exec -T airflow-webserver airflow dags list 2>/dev/null | grep -q "churn_platform_main"; then
    echo -e "  ${GREEN}✓${NC} Airflow (http://localhost:8080)"
else
    echo -e "  ${YELLOW}⚠${NC} Airflow DAG loading (check http://localhost:8080 in 30 seconds)"
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Setup Complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo ""

echo "Next steps:"
echo ""
echo "1. Load initial data:"
echo -e "   ${YELLOW}docker-compose exec airflow-webserver python tests/phase2/test_data_generation.py${NC}"
echo ""
echo "2. Train initial model:"
echo -e "   ${YELLOW}docker-compose exec airflow-webserver python tests/phase4/test_model_training.py${NC}"
echo ""
echo "3. Make a prediction:"
echo -e "   ${YELLOW}curl http://localhost:8000/predict/1${NC}"
echo ""
echo "4. Access Airflow UI:"
echo -e "   ${YELLOW}http://localhost:8080${NC} (admin/airflow)"
echo ""
echo "5. Run full test suite:"
echo -e "   ${YELLOW}make test${NC}"
echo ""

# Create completion marker
echo -e "${BLUE}→${NC} For detailed information, see:"
echo -e "  • docs/FRESH_INSTALLATION.md"
echo -e "  • docs/INSTALLATION_ISSUES.md"
echo ""
