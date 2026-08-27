"""Create and reset the isolated database used by the Playwright suite."""

from __future__ import annotations

import os

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


database_url = os.environ["RFP_LENS_DATABASE_URL"]
url = make_url(database_url)
database_name = url.database
if os.environ.get("RFP_LENS_ENVIRONMENT") != "demo" or not database_name.endswith(
    "_e2e"
):
    raise RuntimeError("E2E database reset is allowed only for the demo *_e2e database")

psycopg_url = url.set(drivername="postgresql")
admin_url = psycopg_url.set(database="postgres")
admin_dsn = admin_url.render_as_string(hide_password=False)
with psycopg.connect(admin_dsn, autocommit=True) as connection:
    exists = connection.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)
    ).fetchone()
    if exists is None:
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )

database_dsn = psycopg_url.render_as_string(hide_password=False)
with psycopg.connect(database_dsn, autocommit=True) as connection:
    connection.execute("DROP SCHEMA public CASCADE")
    connection.execute("CREATE SCHEMA public")
