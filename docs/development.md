# Contributor Development & Testing Guide

This guide covers setting up a local development environment, running test suites, and adhering to engineering standards for E.D.I.T.H.

---

## 1. Local Environment Setup

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Git
- Optional: Ollama (for local offline LLM testing)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/Tiyatrotist/E.D.I.T.H.git
   cd E.D.I.T.H
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Linux/macOS:
   source venv/bin/activate
   # Windows:
   .\venv\Scripts\activate
   ```

3. Install core dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Prepare local configuration:
   ```bash
   cp .env.example .env
   ```
   *(Note: Never commit `.env` or files containing live credentials).*

---

## 2. Running Tests

E.D.I.T.H maintains deterministic, offline test suites that do not require external API keys or hardware devices.

### Offline Security and Config Suite (CI Matrix)
To run the fast offline test suites verified by CI:
```bash
# Security defaults
python -B -m unittest discover -s tests -p "test_sync_security_defaults.py" -v

# Configuration privacy & validation
python -B -m unittest discover -s tests -p "test_config_validation.py" -v
```

### Full Test Suite (pytest)
To execute all local unit and regression tests:
```bash
python -m pytest tests
```

---

## 3. Code Standards & Pull Requests

- **Type Annotations**: Use Python 3.10+ type annotations (`from __future__ import annotations`).
- **No Hardcoded Paths or PII**: Always use dynamic path helpers (`pathlib.Path.home()`, `Path.cwd()`) rather than machine-specific paths.
- **Fail-Closed Principle**: Default all remote and external communication to opt-in.
- **Tests First**: Accompany any bug fix or new feature with deterministic unit tests.
- **Commit Formatting**: Follow conventional commits (e.g. `fix: ...`, `feat: ...`, `docs: ...`, `test: ...`).
