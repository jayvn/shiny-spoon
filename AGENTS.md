# Repository Guidelines
# NO DEFENSIVE PROGRAMMING
# KEEP IT SHORT AND SIMPLE
# ITS ONLY PAPER TRADING ACCOUNT
## Project Structure & Module Organization
- `run_basic.py` — main script for the simple options strategy (entry point).
- `requirements.txt` — Python dependencies.
- `README.md` — strategy overview and usage.
- Generated at runtime: `state_<TICKER>.pkl`, `trades_<TICKER>.csv`.
- Future modules may live under a package (e.g., `pmcc_strategy/`) referenced in README; use snake_case module names and keep files small and focused.

## Build, Test, and Development Commands
- Create env: `python -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Run locally: `python run_basic.py`
- Nix/direnv: `nix-shell` or `direnv allow` (see `shell.nix`/`.envrc`).
- IB setup: Ensure IB Gateway/TWS is running and API enabled on `127.0.0.1:4002` (edit `PORT`, `TICKER`, `DTE_DAYS` at top of `run_basic.py`).

## Coding Style & Naming Conventions
- Python 3; follow PEP 8; 4‑space indentation; type hints required for public functions.
- Naming: snake_case for files/functions, PascalCase for classes, UPPER_CASE for constants.
- Prefer f-strings, early returns, and small pure functions. Optional tools: `black -l 88`, `ruff`.

## Testing Guidelines
- Framework: `pytest`.
- Layout: place tests in `tests/` with files named `test_*.py`.
- Run: `pytest -q` (aim to keep tests fast and deterministic).
- Mock IB interactions; do not hit live APIs in unit tests. Add fixtures for sample option chains and ticks.

## Commit & Pull Request Guidelines
- Commits: imperative mood, concise subject (≤72 chars). Prefer Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- PRs must include: clear description, reproduction/run steps, linked issues, and relevant logs or screenshots. Note any config changes. Ensure code is formatted and tests pass.

## Security & Configuration Tips
- Do not commit generated files (`state_*.pkl`, `trades_*.csv`) or credentials. Consider env vars for ports/IDs.
- Validate all external data; add timeouts around IB calls; log errors clearly.

## Agent-Specific Notes
- Keep changes minimal and scoped; update docs when modifying CLI/behavior. Avoid adding new tooling unless necessary.
