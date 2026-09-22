# Security Policy

E.D.I.T.H is a privacy-first local AI assistant with features that can access local files,
memory, browser automation, shell execution, messaging, audio, and optional remote services.
Security and privacy reports are therefore treated as first-class maintenance work.

## Supported code

Security fixes target the current `main` branch. Older snapshots and forks may not receive
backported fixes.

## Reporting a vulnerability

Please do **not** open a public issue containing credentials, private data, exploit details,
personal paths, message contents, phone numbers, access tokens, or other sensitive material.

For a non-sensitive hardening suggestion, open a normal GitHub issue and use the
`security` label when appropriate.

For a potentially exploitable vulnerability or a report containing sensitive information,
contact the maintainer privately through the contact method listed on the maintainer's
GitHub profile. Include only the minimum information needed to reproduce the problem.

## Security expectations for contributors

- Never commit real API keys, tokens, passwords, phone numbers, personal memory data, or
  machine-specific private files.
- Keep network access opt-in when a feature can transmit user data.
- Prefer fail-closed defaults for remote synchronization and automation boundaries.
- Tests must use synthetic data and should avoid live services where practical.
- Treat shell execution, browser automation, messaging, remote sync, memory, and file
  operations as security-sensitive code.
- Avoid echoing raw configuration values in logs or validation errors.
- Do not weaken existing safety checks merely to simplify testing.

## Scope

Reports involving local data exposure, credential leakage, unsafe command execution,
unexpected network transmission, authentication/authorization failures, or privacy
regressions are in scope.
