from __future__ import annotations

from psycopg_pool import ConnectionPool

from ..config import Config


def make_pool(cfg: Config) -> ConnectionPool:
    # Note: psycopg_pool comes with psycopg (not the legacy psycopg2)
    dsn = (
        f"host={cfg.db_host} port={cfg.db_port} dbname={cfg.db_name} "
        f"user={cfg.db_user} password={cfg.db_pass}"
    )
    return ConnectionPool(conninfo=dsn, min_size=1, max_size=5, open=True)

