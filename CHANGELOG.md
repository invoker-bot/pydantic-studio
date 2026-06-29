# Changelog

All notable user-facing changes are recorded here.

## 0.4.0 - Alpha

- Ships the Interactive editor for Pydantic models across console prompts,
  Textual TUI, and the React-backed local web app.
- Supports YAML round-trip editing with comments, plus TOML and JSON I/O.
- Adds root model variants, task-oriented submit/cancel sessions, parse-on-load
  symmetry for validator-backed fields, and embeddable renderer entry points.
- Hardens release readiness with Python 3.11-3.14 default tests, explicit
  Playwright browser e2e tests, frontend bundle drift checks,
  wheel and sdist install smoke gates, distribution metadata checks,
  GitHub OIDC Trusted Publishing, and independent piesource publishing.
