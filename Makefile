.PHONY: help install check-coverage data test clean

help:
	@echo "Available targets:"
	@echo "  make install        - Install pinned python dependencies"
	@echo "  make check-coverage - Audit OpenAQ sensor coverage for candidate cities"
	@echo "  make fetch          - Fetch raw data from APIs (PM2.5 + Weather)"
	@echo "  make data           - Rebuild warehouse layers from scratch (raw -> cleaned -> processed)"
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

test:
	pytest tests/ -v

clean:
	rm -rf __pycache__ .pytest_cache
