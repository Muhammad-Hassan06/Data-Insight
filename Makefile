.PHONY: help install check-coverage data test clean

help:
	@echo "Available targets:"
	@echo "  make install        - Install pinned python dependencies"
	@echo "  make check-coverage - Audit OpenAQ sensor coverage for candidate cities"
	@echo "  make fetch          - Fetch raw data from APIs (PM2.5 + Weather)"
	@echo "  make data           - Rebuild warehouse layers from scratch (raw -> cleaned -> processed)"
	@echo "  make backend        - Launch FastAPI backend server (port 8000)"
	@echo "  make frontend       - Launch Vite React frontend dashboard (port 5173)"
	@echo "  make test           - Run test suite"
	@echo "  make clean          - Remove temporary caches"

install:
	pip install -r requirements.txt

check-coverage:
	python -m src.fetch.openaq_coverage

fetch:
	python -m src.fetch.fetch_all

data:
	@echo "Running end-to-end data build..."
	python -m src.fetch.fetch_all
	python -m src.clean.build_cleaned
	python -m src.process.build_processed

backend:
	uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	npm --prefix frontend run dev

test:
	pytest tests/ -v

clean:
	rm -rf __pycache__ .pytest_cache
