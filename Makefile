.PHONY: help install check-coverage data test clean

help:
	@echo "Available targets:"
	@echo "  make install        - Install pinned python dependencies"
	@echo "  make check-coverage - Audit OpenAQ sensor coverage for candidate cities"
	@echo "  make data           - Rebuild warehouse layers from scratch (raw -> cleaned -> processed)"
	@echo "  make test           - Run test suite"
	@echo "  make clean          - Remove temporary caches"

install:
	pip install -r requirements.txt

check-coverage:
	python -m src.fetch.openaq_coverage

data:
	@echo "Running end-to-end data build..."
	python -m src.fetch.manifest_verifier
	python -m src.fetch.fetch_all
	python -m src.clean.build_cleaned
	python -m src.process.build_processed
	python -m src.dq_agent.run_gates

test:
	pytest tests/ -v

clean:
	rm -rf __pycache__ .pytest_cache
