"""Postgres connection helper. DSN from CODEORACLE_DB_URL."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg


def dsn() -> str:
    v = os.environ.get("CODEORACLE_DB_URL")
    if not v:
        raise RuntimeError("CODEORACLE_DB_URL not set; source .env or export it")
    return v


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    with psycopg.connect(dsn()) as conn:
        yield conn
