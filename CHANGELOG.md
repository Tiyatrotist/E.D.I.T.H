# Changelog

All notable changes to E.D.I.T.H are documented here.

The project is currently in beta. Release entries describe tested repository state and do not imply that every optional integration is production-ready.

## [Unreleased]

### Planned

- Broader deterministic tests for action and utility modules.
- Contributor-facing configuration documentation.
- A reproducible Windows development and troubleshooting workflow.

## [0.1.0-beta.1] - 2026-09-23

Initial tagged public beta.

### Added

- Multi-provider LLM routing with local/offline operation through Ollama.
- Voice, vision, desktop automation, plugins, reminders, calendar, browser, dashboard, Discord, and companion-device integrations.
- Local configuration validation that runs without contacting live services.
- Offline CI on Python 3.10, 3.11, and 3.12.
- Contributor onboarding, pull-request guidance, and a security policy.

### Security and privacy

- Remote synchronization is opt-in by default and fails closed when configuration is missing.
- Configuration validation no longer reflects raw invalid values in error messages.
- Local API-key configuration and memory files are no longer tracked in the current repository tree.
- Focused privacy/security regression tests run without credentials or live services.

### Community

- Accepted the project's first merged external pull request.
- Added focused good-first issues and contributor documentation.
