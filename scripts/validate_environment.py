from __future__ import annotations

import argparse
import os
import sys

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

from alembic import command

DEFAULT_REQUIRED_TABLES = [
    "system_component",
    "code_repo",
    "pull_request",
    "commit",
    "deployment",
    "runtime_snapshot",
    "api_contract",
    "endpoint",
    "dependency",
    "sync_run",
    "connector_raw_event",
    "connector_sync_state",
    "integration_target_mapping",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate DB environment by applying Alembic migrations and checking expected tables."
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Database URL override. Defaults to DATABASE_URL from environment/.env.",
    )
    parser.add_argument(
        "--alembic-ini",
        default="alembic.ini",
        help="Path to alembic.ini (default: alembic.ini).",
    )
    parser.add_argument(
        "--required-table",
        action="append",
        dest="required_tables",
        default=[],
        help="Required table name. May be provided multiple times.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(dotenv_path=".env")

    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL is not set.")
        return 1

    cfg = Config(args.alembic_ini)
    cfg.set_main_option("sqlalchemy.url", database_url)

    print("Applying migrations: alembic upgrade head")
    command.upgrade(cfg, "head")

    script = ScriptDirectory.from_config(cfg)
    head_revision = script.get_current_head()
    engine = create_engine(database_url)
    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        current_revision = migration_context.get_current_revision()
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())

    if current_revision != head_revision:
        print(
            f"ERROR: database revision mismatch (current={current_revision}, head={head_revision})"
        )
        return 1

    required_tables = args.required_tables or DEFAULT_REQUIRED_TABLES
    missing = [table for table in required_tables if table not in table_names]
    if missing:
        print(f"ERROR: missing tables: {', '.join(missing)}")
        return 1

    print(f"OK: current revision is head ({head_revision})")
    print("OK: required tables present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
