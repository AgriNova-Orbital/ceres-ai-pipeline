.PHONY: up down reset logs test uv-sync uv-test dev-up dev-down dev-logs beta-up beta-down beta-logs release-up release-down release-logs

uv-sync:
	uv sync --dev --extra ml --extra distributed

uv-test:
	uv run --dev pytest -q

up: dev-up

down: dev-down

reset:
	docker compose --profile dev down -v
	docker compose --profile dev up -d --build

logs: dev-logs

test: uv-test

dev-up:
	docker compose --profile dev up -d --build

dev-down:
	docker compose --profile dev down

dev-logs:
	docker compose --profile dev logs -f

beta-up:
	docker compose --profile beta up -d --build

beta-down:
	docker compose --profile beta down

beta-logs:
	docker compose --profile beta logs -f

release-up:
	docker compose --profile release up -d --build

release-down:
	docker compose --profile release down

release-logs:
	docker compose --profile release logs -f
