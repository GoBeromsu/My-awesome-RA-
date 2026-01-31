# My Awesome RA - Demo Environment Makefile
# Usage: make demo

.PHONY: demo demo-stop demo-reset demo-status demo-logs api api-stop seed-load help

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

# Paths
PROJECT_ROOT := $(shell pwd)
OVERLEAF_DEV := $(PROJECT_ROOT)/overleaf/develop
API_DIR := $(PROJECT_ROOT)/apps/api
SEED_DIR := $(PROJECT_ROOT)/fixtures/seed
API_DATA := $(API_DIR)/data

help: ## Show this help
	@echo "$(GREEN)My Awesome RA - Demo Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'

demo: seed-load ## Start full demo environment (Overleaf + API)
	@echo "$(GREEN)🚀 Starting demo environment...$(NC)"
	@cd $(OVERLEAF_DEV) && bin/dev web webpack &
	@echo "$(YELLOW)⏳ Waiting for Overleaf to start...$(NC)"
	@sleep 10
	@echo "$(GREEN)📦 Starting API server...$(NC)"
	@cd $(API_DIR) && source .venv/bin/activate && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 &
	@echo ""
	@echo "$(GREEN)✅ Demo environment starting!$(NC)"
	@echo "   Overleaf: http://localhost:80"
	@echo "   API:      http://localhost:8000"
	@echo "   Login:    demo@example.com / Demo@2024!Secure"
	@echo ""
	@echo "$(YELLOW)⏳ Wait ~30s for webpack to compile$(NC)"

demo-quick: seed-load ## Start demo (assumes Docker already running)
	@echo "$(GREEN)🚀 Quick start - API only$(NC)"
	@cd $(API_DIR) && source .venv/bin/activate && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

demo-stop: ## Stop all demo services
	@echo "$(YELLOW)🛑 Stopping services...$(NC)"
	@cd $(OVERLEAF_DEV) && docker compose down 2>/dev/null || true
	@pkill -f "uvicorn src.main:app" 2>/dev/null || true
	@echo "$(GREEN)✅ All services stopped$(NC)"

demo-reset: demo-stop ## Full reset (removes volumes)
	@echo "$(RED)⚠️  Resetting demo environment...$(NC)"
	@cd $(OVERLEAF_DEV) && docker compose down -v 2>/dev/null || true
	@rm -rf $(API_DATA)/*
	@echo "$(GREEN)✅ Reset complete. Run 'make demo' to start fresh.$(NC)"

demo-status: ## Check status of all services
	@echo "$(GREEN)📊 Service Status$(NC)"
	@echo ""
	@echo "Docker Containers:"
	@docker ps --format "  {{.Names}}: {{.Status}}" 2>/dev/null | grep -E "develop-" || echo "  No containers running"
	@echo ""
	@echo "API Server:"
	@curl -s http://localhost:8000/health 2>/dev/null && echo " ✅ Running" || echo "  ❌ Not running"
	@echo ""
	@echo "Webpack:"
	@docker compose -f $(OVERLEAF_DEV)/docker-compose.yml logs webpack --tail 3 2>/dev/null | grep -E "compiled|error" || echo "  Status unknown"

demo-logs: ## Show webpack logs (follow)
	@docker compose -f $(OVERLEAF_DEV)/docker-compose.yml logs webpack -f

seed-load: ## Load seed data to API data directory
	@echo "$(GREEN)📦 Loading seed data...$(NC)"
	@mkdir -p $(API_DATA)
	@if [ -d "$(SEED_DIR)" ]; then \
		cp -r $(SEED_DIR)/* $(API_DATA)/ 2>/dev/null || true; \
		echo "  Copied seed files to $(API_DATA)"; \
	else \
		echo "  $(YELLOW)Warning: No seed directory found$(NC)"; \
	fi

api: ## Start API server only
	@echo "$(GREEN)🔧 Starting API server...$(NC)"
	@cd $(API_DIR) && source .venv/bin/activate && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

api-stop: ## Stop API server
	@pkill -f "uvicorn src.main:app" 2>/dev/null || true
	@echo "$(GREEN)✅ API server stopped$(NC)"

test-api: ## Run API tests
	@echo "$(GREEN)🧪 Running API tests...$(NC)"
	@cd $(API_DIR) && pytest -v --tb=short

test-frontend: ## Run frontend tests (inside Docker)
	@echo "$(GREEN)🧪 Running frontend tests...$(NC)"
	@docker exec develop-web-1 sh -c "cd /overleaf/services/web && npm run test:frontend -- --grep 'Evidence'"

user-create: ## Create demo user (after volume reset)
	@echo "$(GREEN)👤 Creating demo user...$(NC)"
	@docker compose -f $(OVERLEAF_DEV)/docker-compose.yml exec web bash -c \
		"cd /overleaf/services/web && node modules/server-ce-scripts/scripts/create-user.js --email=demo@example.com --admin"
	@echo "$(YELLOW)Set password to: Demo@2024!Secure$(NC)"
