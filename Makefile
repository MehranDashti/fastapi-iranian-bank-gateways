.PHONY: install test lint type-check format coverage build clean pre-commit

install:
	pip install -e ".[dev,soap]"

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

type-check:
	mypy src/

format:
	ruff format src/ tests/
	ruff check src/ tests/ --fix

coverage:
	pytest --cov --cov-report=html --cov-fail-under=80
	@echo "HTML report: htmlcov/index.html"

build:
	python -m build

clean:
	rm -rf dist/ build/ htmlcov/ .coverage .coverage.*
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -name "*.pyc" -delete

pre-commit:
	pre-commit install
	pre-commit run --all-files
