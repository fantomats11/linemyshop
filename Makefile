BACKEND_DIR := apps/backend

.PHONY: install dev migrate test db-up db-down

install:
	@if command -v uv >/dev/null 2>&1; then \
		cd $(BACKEND_DIR) && uv sync --dev; \
	else \
		cd $(BACKEND_DIR) && python3 -m venv .venv && . .venv/bin/activate && pip install --upgrade pip && pip install -e ".[dev]"; \
	fi

dev:
	@if command -v uv >/dev/null 2>&1; then \
		cd $(BACKEND_DIR) && uv run uvicorn app.main:app --reload; \
	else \
		cd $(BACKEND_DIR) && . .venv/bin/activate && uvicorn app.main:app --reload; \
	fi

migrate:
	@if command -v uv >/dev/null 2>&1; then \
		cd $(BACKEND_DIR) && uv run alembic upgrade head; \
	else \
		cd $(BACKEND_DIR) && . .venv/bin/activate && alembic upgrade head; \
	fi

test:
	@if command -v uv >/dev/null 2>&1; then \
		cd $(BACKEND_DIR) && uv run pytest; \
	else \
		cd $(BACKEND_DIR) && . .venv/bin/activate && pytest; \
	fi

db-up:
	docker compose up -d postgres

db-down:
	docker compose down
