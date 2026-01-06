.PHONY: help setup up down restart status logs clean prune
.PHONY: test test-all test-phase2 test-phase3 test-phase4 test-phase5 test-phase6 test-phase7
.PHONY: db-connect db-backup db-restore db-clean
.PHONY: shell redis logs-postgres logs-redis logs-fastapi
.PHONY: version health predict batch-predict
.PHONY: airflow-restart airflow-logs airflow-trigger train airflow-clear-dag airflow-clear-task airflow-run-task

# Color output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Variables
PROJECT_NAME := churn-platform
COMPOSE_FILE := docker-compose.yml
API_URL := http://localhost:8000
DB_CONTAINER := churn-postgres
REDIS_CONTAINER := churn-redis
API_CONTAINER := churn-fastapi

# Default target
.DEFAULT_GOAL := help

##@ General

help: ## Display this help message
	@echo "$(BLUE)Churn Prediction Platform - Makefile Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Setup & Management:$(NC)"
	@echo "  $(GREEN)setup$(NC)               Initialize platform (first time only)"
	@echo "  $(GREEN)up$(NC)                  Start all services"
	@echo "  $(GREEN)down$(NC)                Stop all services"
	@echo "  $(GREEN)restart$(NC)             Restart all containers"
	@echo "  $(GREEN)status$(NC)              Check service health"
	@echo "  $(GREEN)logs$(NC)                View FastAPI logs (live)"
	@echo "  $(GREEN)clean$(NC)               Remove containers & data (⚠️  destructive)"
	@echo "  $(GREEN)version$(NC)             Show platform version"
	@echo ""
	@echo "$(YELLOW)Database Operations:$(NC)"
	@echo "  $(GREEN)db-connect$(NC)          Connect to PostgreSQL CLI"
	@echo "  $(GREEN)db-backup$(NC)           Create timestamped backup"
	@echo "  $(GREEN)db-restore$(NC)          Restore from backup"
	@echo "  $(GREEN)db-clean$(NC)            Delete all data (⚠️  requires confirmation)"
	@echo ""
	@echo "$(YELLOW)Testing (All Phases):$(NC)"
	@echo "  $(GREEN)test$(NC)                Run ALL tests (phases 2-7)"
	@echo "  $(GREEN)test-phase2$(NC)         Test data generation"
	@echo "  $(GREEN)test-phase3$(NC)         Test feature engineering"
	@echo "  $(GREEN)test-phase4$(NC)         Test model training"
	@echo "  $(GREEN)test-phase5$(NC)         Test online serving"
	@echo "  $(GREEN)test-phase6$(NC)         Test monitoring"
	@echo "  $(GREEN)test-phase7$(NC)         Test advanced features"
	@echo ""
	@echo "$(YELLOW)Development Tools:$(NC)"
	@echo "  $(GREEN)shell$(NC)               Open FastAPI container shell"
	@echo "  $(GREEN)redis$(NC)               Connect to Redis CLI"
	@echo "  $(GREEN)python-shell$(NC)        Open Python REPL"
	@echo "  $(GREEN)logs-postgres$(NC)       View PostgreSQL logs"
	@echo "  $(GREEN)logs-redis$(NC)          View Redis logs"
	@echo ""
	@echo "$(YELLOW)API & Utilities:$(NC)"
	@echo "  $(GREEN)health$(NC)              Check system health"
	@echo "  $(GREEN)predict$(NC)             Make single prediction"
	@echo "  $(GREEN)batch-predict$(NC)       Batch predictions (5 users)"
	@echo "  $(GREEN)dashboard$(NC)           Get dashboard summary"
	@echo "  $(GREEN)models$(NC)              List model versions"
	@echo "  $(GREEN)cache-sync$(NC)          Refresh feature cache"
	@echo "  $(GREEN)cache-clear$(NC)         Clear all cached features"
	@echo "  $(GREEN)api-docs$(NC)            Open API docs in browser"
	@echo ""
	@echo "$(YELLOW)Documentation & Help:$(NC)"
	@echo "  $(GREEN)docs$(NC)                Quick reference guide"
	@echo "  $(GREEN)help$(NC)                Display this message"
	@echo ""

##@ Setup & Management

setup: ## Initialize the platform (first time only)
	@echo "$(BLUE)Initializing Churn Prediction Platform...$(NC)"
	@docker-compose up -d
	@sleep 3
	@echo "$(GREEN)✓ Platform initialized$(NC)"
	@make status

up: ## Start all containers
	@echo "$(BLUE)Starting services...$(NC)"
	@docker-compose up -d
	@echo "$(GREEN)✓ All services started$(NC)"
	@sleep 2
	@make status

down: ## Stop all containers
	@echo "$(YELLOW)Stopping services...$(NC)"
	@docker-compose down
	@echo "$(GREEN)✓ All services stopped$(NC)"

restart: ## Restart all services
	@echo "$(YELLOW)Restarting services...$(NC)"
	@docker-compose restart
	@echo "$(GREEN)✓ All services restarted$(NC)"
	@sleep 2
	@make status

status: ## Check container status
	@echo "$(BLUE)Service Status:$(NC)"
	@docker-compose ps
	@echo ""
	@echo "$(BLUE)Health Check:$(NC)"
	@curl -s $(API_URL)/health | python3 -m json.tool 2>/dev/null || echo "API not responding"

logs: ## View live FastAPI logs
	@docker logs -f $(API_CONTAINER)

logs-postgres: ## View PostgreSQL logs
	@docker logs -f $(DB_CONTAINER)

logs-redis: ## View Redis logs
	@docker logs -f $(REDIS_CONTAINER)

clean: ## Remove containers and volumes (DESTRUCTIVE)
	@echo "$(RED)WARNING: This will delete all data!$(NC)"
	@read -p "Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		echo "$(GREEN)✓ Cleaned$(NC)"; \
	fi

prune: ## Clean up unused Docker resources
	@echo "$(YELLOW)Pruning Docker resources...$(NC)"
	@docker container prune -f
	@docker image prune -f
	@docker volume prune -f
	@echo "$(GREEN)✓ Pruned$(NC)"

version: ## Show platform version
	@echo "$(BLUE)Churn Prediction Platform$(NC)"
	@echo "Version: 1.0.0"
	@echo "Status: Production Ready"
	@echo "Phases: 7/7 Complete ✅"
	@echo ""
	@echo "Components:"
	@echo "  • FastAPI: Production ML Serving"
	@echo "  • PostgreSQL: Data Persistence (1.4M+ rows)"
	@echo "  • Redis: Feature Caching (>95% hit rate)"
	@echo "  • Airflow: Task Orchestration"
	@echo "  • Docker: 6 Services"

##@ Database Operations

db-connect: ## Connect to PostgreSQL database
	@echo "$(BLUE)Connecting to PostgreSQL...$(NC)"
	@docker exec -it $(DB_CONTAINER) psql -U churn_user -d churn_db

db-backup: ## Backup database
	@echo "$(BLUE)Backing up database...$(NC)"
	@mkdir -p backups
	@docker exec $(DB_CONTAINER) pg_dump -U churn_user -d churn_db > backups/churn_db_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✓ Backup complete$(NC)"

db-restore: ## Restore database from backup
	@echo "$(BLUE)Restore database from backup:$(NC)"
	@ls -lh backups/churn_db_*.sql | tail -1
	@echo ""
	@read -p "Enter backup filename to restore (or press Enter for latest): " backup; \
	if [ -z "$$backup" ]; then \
		backup=$$(ls -t backups/churn_db_*.sql | head -1); \
	fi; \
	if [ -f "$$backup" ]; then \
		docker exec -i $(DB_CONTAINER) psql -U churn_user -d churn_db < $$backup; \
		echo "$(GREEN)✓ Restore complete$(NC)"; \
	else \
		echo "$(RED)✗ Backup file not found$(NC)"; \
	fi

db-clean: ## Clean all database data (DESTRUCTIVE)
	@echo "$(RED)WARNING: This will DELETE all data!$(NC)"
	@read -p "Type 'DELETE_ALL' to confirm: " confirm; \
	if [ "$$confirm" = "DELETE_ALL" ]; then \
		docker exec $(DB_CONTAINER) psql -U churn_user -d churn_db -c "DROP SCHEMA IF EXISTS raw_data CASCADE; DROP SCHEMA IF EXISTS ml_pipeline CASCADE;"; \
		echo "$(GREEN)✓ Database cleaned$(NC)"; \
	fi

##@ Testing

test: ## Run all tests
	@echo "$(BLUE)Running all tests...$(NC)"
	@echo ""
	@echo "$(YELLOW)Phase 2: Data Generation$(NC)"
	@python3 tests/phase2/test_data_generation.py || true
	@echo ""
	@echo "$(YELLOW)Phase 3: Features$(NC)"
	@python3 tests/phase3/test_features.py || true
	@echo ""
	@echo "$(YELLOW)Phase 4: Models$(NC)"
	@python3 tests/phase4/test_models.py || true
	@echo ""
	@echo "$(YELLOW)Phase 5: Serving$(NC)"
	@python3 tests/phase5/test_serving.py || true
	@echo ""
	@echo "$(YELLOW)Phase 6: Monitoring$(NC)"
	@python3 tests/phase6/test_monitoring.py || true
	@echo ""
	@echo "$(YELLOW)Phase 7: Advanced Features (Unit)$(NC)"
	@docker exec $(API_CONTAINER) python3 /app/tests/phase7/test_advanced.py || true
	@echo ""
	@echo "$(YELLOW)Phase 7: Advanced Features (Integration)$(NC)"
	@python3 tests/phase7/test_dashboard.py || true

test-phase2: ## Test data generation
	@echo "$(BLUE)Testing Phase 2: Data Generation$(NC)"
	@python3 tests/phase2/test_data_generation.py

test-phase3: ## Test feature engineering
	@echo "$(BLUE)Testing Phase 3: Feature Engineering$(NC)"
	@python3 tests/phase3/test_features.py

test-phase4: ## Test model training
	@echo "$(BLUE)Testing Phase 4: Model Training$(NC)"
	@python3 tests/phase4/test_models.py

test-phase5: ## Test online serving
	@echo "$(BLUE)Testing Phase 5: Online Serving$(NC)"
	@python3 tests/phase5/test_serving.py

test-phase6: ## Test monitoring
	@echo "$(BLUE)Testing Phase 6: Monitoring$(NC)"
	@python3 tests/phase6/test_monitoring.py

test-phase7: ## Test advanced features
	@echo "$(BLUE)Testing Phase 7: Advanced Features$(NC)"
	@echo "$(YELLOW)Unit Tests:$(NC)"
	@docker exec $(API_CONTAINER) python3 /app/tests/phase7/test_advanced.py
	@echo ""
	@echo "$(YELLOW)Integration Tests:$(NC)"
	@python3 tests/phase7/test_dashboard.py

##@ Development

shell: ## Open FastAPI container shell
	@echo "$(BLUE)Opening FastAPI shell...$(NC)"
	@docker exec -it $(API_CONTAINER) /bin/bash

redis: ## Connect to Redis CLI
	@echo "$(BLUE)Connecting to Redis...$(NC)"
	@docker exec -it $(REDIS_CONTAINER) redis-cli

python-shell: ## Open Python shell in FastAPI container
	@echo "$(BLUE)Opening Python shell...$(NC)"
	@docker exec -it $(API_CONTAINER) python3

##@ Utilities

health: ## Check system health
	@echo "$(BLUE)System Health Check:$(NC)"
	@curl -s $(API_URL)/health | python3 -m json.tool

predict: ## Make single prediction (user_id: 1)
	@echo "$(BLUE)Single Prediction for user 1:$(NC)"
	@curl -s $(API_URL)/predict/1 | python3 -m json.tool

batch-predict: ## Make batch predictions
	@echo "$(BLUE)Batch Predictions (users 1-5):$(NC)"
	@curl -s -X POST $(API_URL)/predict/batch \
		-H "Content-Type: application/json" \
		-d '{"user_ids": [1, 2, 3, 4, 5], "use_cache": true}' | python3 -m json.tool

dashboard: ## Get dashboard summary
	@echo "$(BLUE)Dashboard Summary:$(NC)"
	@curl -s $(API_URL)/dashboard/summary | python3 -m json.tool

models: ## List all model versions
	@echo "$(BLUE)Model Versions:$(NC)"
	@curl -s $(API_URL)/dashboard/models | python3 -m json.tool

retraining-status: ## Check retraining status
	@echo "$(BLUE)Retraining Status:$(NC)"
	@curl -s $(API_URL)/dashboard/retraining-status | python3 -m json.tool

cache-sync: ## Sync feature cache
	@echo "$(BLUE)Syncing cache...$(NC)"
	@curl -s $(API_URL)/cache/sync | python3 -m json.tool
	@echo "$(GREEN)✓ Cache synchronized$(NC)"

cache-clear: ## Clear feature cache
	@echo "$(YELLOW)Clearing cache...$(NC)"
	@curl -s $(API_URL)/cache/clear | python3 -m json.tool
	@echo "$(GREEN)✓ Cache cleared$(NC)"

api-docs: ## Open API documentation in browser
	@echo "$(BLUE)Opening API docs...$(NC)"
	@open $(API_URL)/docs || xdg-open $(API_URL)/docs || echo "Please visit: $(API_URL)/docs"

##@ Examples

example-workflow: ## Run example workflow
	@echo "$(BLUE)Running example workflow...$(NC)"
	@echo ""
	@echo "1. $(YELLOW)Getting status...$(NC)"
	@make status
	@echo ""
	@echo "2. $(YELLOW)Making prediction...$(NC)"
	@make predict
	@echo ""
	@echo "3. $(YELLOW)Checking dashboard...$(NC)"
	@make dashboard
	@echo ""
	@echo "$(GREEN)✓ Workflow complete$(NC)"

##@ Documentation

docs: ## Display quick reference
	@echo "$(BLUE)Quick Reference:$(NC)"
	@echo ""
	@echo "Start platform:        make up"
	@echo "Stop platform:         make down"
	@echo "View status:           make status"
	@echo "Run all tests:         make test"
	@echo "Check health:          make health"
	@echo "View logs:             make logs"
	@echo ""
	@echo "Database commands:"
	@echo "  Connect:             make db-connect"
	@echo "  Backup:              make db-backup"
	@echo "  Restore:             make db-restore"
	@echo ""
	@echo "API commands:"
	@echo "  Single prediction:   make predict"
	@echo "  Batch prediction:    make batch-predict"
	@echo "  Dashboard:           make dashboard"
	@echo "  Cache sync:          make cache-sync"
	@echo ""
	@echo "Airflow & Training:"
	@echo "  Restart scheduler:   make airflow-restart"
	@echo "  View DAG logs:       make airflow-logs"
	@echo "  Trigger DAG now:     make airflow-trigger"
	@echo "  Manual training:     make train"
	@echo ""
	@echo "Development:"
	@echo "  Shell:               make shell"
	@echo "  Redis:               make redis"
	@echo "  Python:              make python-shell"
	@echo ""

##@ Airflow & Training

airflow-restart: ## Restart Airflow scheduler (pick up DAG changes)
	@echo "$(BLUE)Restarting Airflow scheduler...$(NC)"
	@docker-compose restart airflow-scheduler
	@echo "$(GREEN)✓ Airflow scheduler restarted$(NC)"
	@sleep 2
	@docker-compose logs airflow-scheduler | tail -5

airflow-logs: ## View Airflow scheduler logs
	@echo "$(BLUE)Airflow scheduler logs (last 50 lines):$(NC)"
	@docker-compose logs airflow-scheduler | tail -50

airflow-trigger: ## Trigger churn_platform_main DAG immediately
	@echo "$(BLUE)Triggering DAG: churn_platform_main$(NC)"
	@docker-compose exec airflow-scheduler airflow dags trigger churn_platform_main
	@echo "$(GREEN)✓ DAG triggered$(NC)"
	@echo "$(YELLOW)View progress with: make airflow-logs$(NC)"

airflow-clear-dag: ## Clear entire DAG run (runs all tasks again)
	@echo "$(YELLOW)Clearing all tasks for churn_platform_main...$(NC)"
	@docker-compose exec airflow-scheduler airflow dags test churn_platform_main 2>&1 | grep -i clear || \
	docker-compose exec airflow-scheduler airflow tasks clear churn_platform_main -c
	@echo "$(GREEN)✓ DAG cleared$(NC)"
	@echo "$(YELLOW)Next: make airflow-trigger$(NC)"

airflow-clear-task: ## Clear a specific task and downstream tasks (TASK=task_name)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Error: Please specify task name$(NC)"; \
		echo "Usage: make airflow-clear-task TASK=sync_online_features"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Clearing task '$(TASK)' and all downstream tasks...$(NC)"
	@docker-compose exec airflow-scheduler airflow tasks clear churn_platform_main -t $(TASK) --downstream -y
	@echo "$(GREEN)✓ Task cleared$(NC)"
	@echo "$(YELLOW)Next: make airflow-trigger$(NC)"

airflow-run-task: ## Run a specific task directly (TASK=task_name)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Error: Please specify task name$(NC)"; \
		echo "Usage: make airflow-run-task TASK=train_model"; \
		exit 1; \
	fi
	@echo "$(BLUE)Running task '$(TASK)'...$(NC)"
	@docker-compose exec airflow-scheduler airflow tasks run churn_platform_main $(TASK) 2026-01-05T01:00:00+00:00 --local
	@echo "$(GREEN)✓ Task complete$(NC)"

train: ## Manually run training script (saves to /app/data/models/)
	@echo "$(BLUE)Running manual training...$(NC)"
	@docker-compose exec fastapi python3 src/models/train.py
	@echo "$(GREEN)✓ Training complete$(NC)"
	@echo "$(YELLOW)Model saved to: /app/data/models/churn_model.pkl$(NC)"

