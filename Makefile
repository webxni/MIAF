SHELL := /bin/bash

COMPOSE      := docker compose
COMPOSE_PROD := docker compose -f compose.yaml -f compose.prod.yaml

.DEFAULT_GOAL := help

.PHONY: help env up down build rebuild logs ps restart clean \
        api-shell web-shell db-shell redis-shell \
        api-logs web-logs worker-logs scheduler-logs \
        prod-up prod-down prod-build smoke \
        migrate seed test bootstrap revision \
        tailscale-status tailscale-ip tailscale-serve tailscale-serve-status tailscale-serve-reset

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

env: ## Copy .env.example -> .env if missing
	@test -f .env || cp .env.example .env && echo ".env created from .env.example — edit secrets before running."

up: ## Start dev stack (detached)
	$(COMPOSE) up -d

down: ## Stop dev stack
	$(COMPOSE) down

build: ## Build dev images
	$(COMPOSE) build

rebuild: ## Rebuild dev images without cache
	$(COMPOSE) build --no-cache

logs: ## Tail all logs
	$(COMPOSE) logs -f --tail=100

ps: ## Show service status
	$(COMPOSE) ps

restart: ## Restart all services
	$(COMPOSE) restart

clean: ## Stop and DELETE all volumes (DESTRUCTIVE)
	$(COMPOSE) down -v

api-shell: ## Bash into api container
	$(COMPOSE) exec api /bin/bash

web-shell: ## Sh into web container
	$(COMPOSE) exec web /bin/sh

db-shell: ## psql into postgres
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-miaf} -d $${POSTGRES_DB:-miaf}

redis-shell: ## redis-cli into redis (uses REDIS_PASSWORD)
	$(COMPOSE) exec redis sh -c 'redis-cli -a "$$REDIS_PASSWORD"'

api-logs: ; $(COMPOSE) logs -f --tail=100 api
web-logs: ; $(COMPOSE) logs -f --tail=100 web
worker-logs: ; $(COMPOSE) logs -f --tail=100 worker
scheduler-logs: ; $(COMPOSE) logs -f --tail=100 scheduler

smoke: ## Curl health endpoints (requires `make up` first)
	@echo "GET /health"
	@curl -fsS http://localhost:$${HTTP_PORT:-80}/api/health && echo
	@echo "GET /health/ready"
	@curl -fsS http://localhost:$${HTTP_PORT:-80}/api/health/ready && echo

migrate: ## Apply database migrations (alembic upgrade head)
	$(COMPOSE) exec -T api python -m app.cli migrate

seed: ## Seed default tenant, user, entities, and charts of accounts (idempotent)
	$(COMPOSE) exec -T api python -m app.cli seed

test: ## Run api tests inside the api container (uses miaf_test database)
	$(COMPOSE) exec -T api pytest -q

revision: ## Generate an Alembic revision: make revision m="add foo"
	@test -n "$(m)" || (echo "usage: make revision m=\"message\"" && exit 1)
	$(COMPOSE) exec -T api alembic revision --autogenerate -m "$(m)"

bootstrap: up migrate seed ## Up the stack, run migrations, seed

prod-up: ## Start production stack (detached)
	$(COMPOSE_PROD) up -d --build

prod-down: ## Stop production stack
	$(COMPOSE_PROD) down

prod-build: ## Build production images
	$(COMPOSE_PROD) build

# ── Tailscale helpers (run on the host, not inside a container) ───────────────

tailscale-status: ## Show Tailscale connection status (JSON)
	tailscale status --json | python3 -m json.tool

tailscale-ip: ## Print this machine's Tailscale IPv4 address
	tailscale ip -4

tailscale-serve: ## Start Tailscale Serve pointing at localhost:80 (private tailnet only)
	sudo tailscale serve --bg http://127.0.0.1:80

tailscale-serve-status: ## Show active Tailscale Serve configuration
	tailscale serve status

tailscale-serve-reset: ## Remove all Tailscale Serve configuration
	sudo tailscale serve reset
