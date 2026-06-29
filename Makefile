.PHONY: up down build migrate test lint typecheck test-all check build-prod up-prod deploy-prod ci

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

migrate:
	docker compose exec backend python manage.py migrate

test:
	docker compose exec backend pytest

lint:
	cd frontend && npm run lint

typecheck:
	cd frontend && npm run typecheck

test-all:
	docker compose exec backend pytest
	cd frontend && npm run test

check:
	cd frontend && npm run check

build-prod:
	docker compose -f docker-compose.prod.yml build

up-prod:
	docker compose -f docker-compose.prod.yml up -d --build

deploy-prod:
	./scripts/deploy-prod.sh

ci: test-all check build-prod
	cd frontend && npm run build