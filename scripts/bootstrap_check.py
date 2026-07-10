"""Environment sanity check.

Run before any scanner task fires. Verifies:
  - project root not on a OneDrive-synced path
  - Python >= 3.11
  - .env exists and has required keys
  - Postgres DSN connects
  - All migrations recorded in schema_migrations

Exit non-zero if any check fails.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_ENV = [
    "CODEORACLE_DB_URL",
    "CODEORACLE_TG_TOKEN",
    "CODEORACLE_TG_CHAT_LIVE",
    "CODEORACLE_TG_CHAT_MUTED",
    "CODEORACLE_TG_CHAT_DIGEST",
    "CODEORACLE_HELIUS_KEY",
    "GATE_LIQ_MIN_USD",
    "POSITION_DEFAULT_USD",
]
MIGRATIONS_DIR = PROJECT_ROOT / "src" / "db" / "migrations"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check_not_onedrive() -> None:
    p = str(PROJECT_ROOT).lower()
    if "onedrive" in p:
        _fail(
            f"project root resolves under OneDrive: {PROJECT_ROOT}. "
            "Move to a non-synced location (e.g. C:\\CodeOracle)."
        )
    print(f"OK: project root {PROJECT_ROOT}")


def check_python() -> None:
    if sys.version_info < (3, 11):
        _fail(f"Python 3.11+ required, got {sys.version_info[:3]}")
    print(f"OK: Python {sys.version.split()[0]}")


def load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        _fail(f".env missing at {env_path}. Copy from .env.example and fill values.")
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
    print(f"OK: .env loaded from {env_path}")


def check_env_keys() -> None:
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k) or os.environ[k] == "REPLACE_ME"]
    if missing:
        _fail(f"env keys missing or unset: {missing}")
    print(f"OK: {len(REQUIRED_ENV)} required env keys present")


def check_db() -> None:
    try:
        import psycopg
    except ImportError:
        _fail("psycopg not installed. Run: pip install -r requirements.txt")
    dsn = os.environ["CODEORACLE_DB_URL"]
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception as e:
        _fail(f"cannot connect to {dsn.split('@')[-1]}: {e}")
    print("OK: Postgres reachable")


def check_migrations() -> None:
    import psycopg

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        _fail(f"no migrations found in {MIGRATIONS_DIR}")
    dsn = os.environ["CODEORACLE_DB_URL"]
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                "WHERE table_name='schema_migrations')"
            )
            has_table = cur.fetchone()[0]
            if not has_table:
                _fail(
                    "schema_migrations table missing. Run migrations: "
                    "psql -d codeoracle -f src/db/migrations/001_init.sql ..."
                )
            cur.execute("SELECT filename FROM schema_migrations")
            applied = {r[0] for r in cur.fetchall()}
    unapplied = [f.name for f in files if f.name not in applied]
    if unapplied:
        _fail(f"unapplied migrations: {unapplied}")
    print(f"OK: {len(files)} migrations applied")


def main() -> None:
    checks = [
        check_not_onedrive,
        check_python,
        load_env,
        check_env_keys,
        check_db,
        check_migrations,
    ]
    for c in checks:
        c()
    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
