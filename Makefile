.PHONY: up down build migrate test lint typecheck

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

migrate:
	cd backend && python manage.py migrate

test:
	cd backend && pytest

lint:
	cd frontend && npm run lint

typecheck:
	cd frontend && npm run typecheck
