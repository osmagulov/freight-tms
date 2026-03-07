.PHONY: install db-up db-down migrate run-api run-bot

install:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

db-up:
	docker-compose up -d

db-down:
	docker-compose down

migrate:
	./venv/bin/alembic revision --autogenerate -m "Initial migration"
	./venv/bin/alembic upgrade head

run-api:
	./venv/bin/uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
