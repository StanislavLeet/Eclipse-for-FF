.PHONY: run test migrate lint install dev-install

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest

test-cov:
	pytest --cov=app --cov-report=term-missing

migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

lint:
	ruff check .

lint-fix:
	ruff check --fix .

install:
	pip install -r requirements.txt

dev-install:
	pip install -r requirements.txt -r requirements-dev.txt

dev-db:
	createdb eclipse_game 2>/dev/null || echo "DB already exists"
