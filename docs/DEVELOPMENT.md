# Development Workflow

## Setup

```bash
pip install -r requirements-dev.txt
```

## Local Checks

```bash
python -m ruff check .
python -m unittest discover -s tests -v
```

## CI

GitHub Actions workflow is available at `.github/workflows/ci.yml`.
It runs linting and unit tests on Python 3.10 and 3.11 (Windows runner).
