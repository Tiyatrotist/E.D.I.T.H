# Open Source Maintenance & Engineering Evidence

This document records factual maintenance, engineering health, and operational readiness metrics for E.D.I.T.H.

---

## 1. Project Identification & Governance

- **Repository**: `Tiyatrotist/E.D.I.T.H`
- **Maintainer**: `Tiyatrotist`
- **License**: MIT License ([LICENSE](file:///C:/Users/Bugra/oss-sprint/repos/E.D.I.T.H/LICENSE))
- **Maturity / Lifecycle Stage**: Active Beta (Semantic Versioning `v0.1.0-beta.1`)
- **Primary Technology Stack**: Python 3.10+, FastAPI, PyQt, SQLite/JSON local persistence

---

## 2. Continuous Integration & Quality Assurance

- **CI Pipeline**: Automated GitHub Actions workflow (`.github/workflows/ci.yml`) executed on all pushes and PRs to `main`.
- **Platform Matrix**: Python 3.10, Python 3.11, Python 3.12 on Linux (`ubuntu-latest`).
- **Offline / Deterministic Test Coverage**:
  - `tests/test_sync_security_defaults.py`: Verifies fail-closed behavior for remote sync endpoints.
  - `tests/test_config_validation.py`: Verifies configuration privacy, type-checking, and zero network leakage during boot.
  - `tests/`: 213 unit and regression tests passing with zero failures.

---

## 3. Security, Privacy & Hygiene Practices

- **Zero Tracked Credentials**: Secrets, API keys, and local configuration files (`config.json`, `config.local.json`, `.env`, `memory/*.json`) are excluded via `.gitignore`.
- **No Path/PII Leaks**: All paths are resolved dynamically using `pathlib.Path.home()` without hardcoded local usernames.
- **Fail-Closed Networking**: Outbound sync is disabled by default; network calls require explicit user opt-in.
- **Vulnerability Reporting**: Coordinated security response policy documented in [SECURITY.md](file:///C:/Users/Bugra/oss-sprint/repos/E.D.I.T.H/SECURITY.md).

---

## 4. Contributor Experience & Documentation

- **Contributor Guidance**: [CONTRIBUTING.md](file:///C:/Users/Bugra/oss-sprint/repos/E.D.I.T.H/CONTRIBUTING.md) and [docs/development.md](file:///C:/Users/Bugra/oss-sprint/repos/E.D.I.T.H/docs/development.md) detailing test commands and PR requirements.
- **Architecture Specification**: [docs/architecture.md](file:///C:/Users/Bugra/oss-sprint/repos/E.D.I.T.H/docs/architecture.md) covering core subsystems, memory vectors, and plugin registry.
- **Changelog**: Detailed release history and unreleased tracking in [CHANGELOG.md](file:///C:/Users/Bugra/oss-sprint/repos/E.D.I.T.H/CHANGELOG.md).
