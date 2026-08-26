# Contributing to E.D.I.T.H

Thank you for your interest in contributing to E.D.I.T.H.

E.D.I.T.H is a privacy-first, local-first AI assistant for Windows. Contributions should preserve the project's offline-first design and avoid introducing unnecessary cloud dependencies.

## Before you start

1. Read the README and existing issues.
2. Check whether an issue already exists for your change.
3. For larger changes, open an issue before submitting a pull request.
4. Keep pull requests focused on one change.

## Development principles

- Prefer local processing and privacy-preserving designs.
- Avoid hard-coded secrets, tokens, personal paths, or machine-specific configuration.
- Keep platform-specific behavior explicit.
- Add or update tests when practical.
- Preserve backward compatibility unless a breaking change is intentional and documented.

## Pull requests

A good pull request should explain:

- what changed;
- why it changed;
- how it was tested;
- any platform or dependency considerations.

Small documentation, testing, typing, reliability, accessibility, and developer-experience improvements are welcome.

## Good first contributions

Look for issues labeled `good first issue` or `help wanted`. Documentation fixes, test coverage, type annotations, CI improvements, and isolated action modules are especially suitable starting points.

## Code quality

Please keep changes readable and consistent with the existing Python codebase. Do not add generated files, caches, credentials, or local environment files to commits.
