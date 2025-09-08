* Repository Guidelines
* NO DEFENSIVE PROGRAMMING
* KEEP IT SHORT AND SIMPLE
* ITS ONLY PAPER TRADING ACCOUNT
* USE RUFF CHECK AND RUFF FORMATTING INCLUDING  import sorting and whatever after each edit
* use basedpyright for checking if code will work 
---

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

source .venv/bin/activate and uv pip install
