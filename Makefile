.PHONY: up down reset logs test

up:
	docker compose up -d

down:
	docker compose down

reset:
	docker compose down -v
	docker compose up -d --build

logs:
	docker compose logs -f

test:
	.venv/bin/python -m pytest tests/e2e/ -v -s
