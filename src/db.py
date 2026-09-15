from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from src.config import get_settings


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as conn:
        yield conn


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict | None:
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict]:
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(sql, params)
        return list(cursor.fetchall())


def execute(sql: str, params: tuple[Any, ...] = ()) -> dict | None:
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(sql, params)
        if cursor.description is None:
            return None
        return cursor.fetchone()


def ensure_schema() -> None:
    """Apply additive migrations so existing Docker volumes remain usable."""
    statements = [
        """
        CREATE TABLE IF NOT EXISTS prompt_versions (
            identity text PRIMARY KEY,
            assistant text NOT NULL,
            variant text NOT NULL,
            full_text text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        "ALTER TABLE prompts ADD COLUMN IF NOT EXISTS prompt_identity text",
        """
        CREATE TABLE IF NOT EXISTS prompt_history (
            assistant text NOT NULL,
            variant text NOT NULL,
            prompt_identity text NOT NULL REFERENCES prompt_versions(identity),
            activated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (assistant, variant, prompt_identity)
        )
        """,
        "ALTER TABLE judge_samples ADD COLUMN IF NOT EXISTS dimension_scores jsonb NOT NULL DEFAULT '{}'::jsonb",
    ]
    with connection() as conn, conn.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
