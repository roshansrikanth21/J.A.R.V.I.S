# Contributing

## Setup
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
pip install -U pip pytest ruff black mypy
```

## Checks
```bash
ruff .
black --check .
mypy src || true
pytest -q
```
