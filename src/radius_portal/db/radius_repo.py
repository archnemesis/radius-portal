from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from psycopg_pool import ConnectionPool


@dataclass(frozen=True)
class RadiusUser:
    username: str
    password: Optional[str]
    expiration: Optional[str]


class RadiusRepo:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    def ensure_schema(self) -> None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT to_regclass('public.radcheck') IS NOT NULL AS has_radcheck,
                       to_regclass('public.radreply') IS NOT NULL AS has_radreply
                """
            )
            has_radcheck, has_radreply = cur.fetchone()
            if not has_radcheck or not has_radreply:
                raise RuntimeError("Missing radcheck/radreply tables. Load FreeRADIUS SQL schema.")

    def list_users(self) -> list[RadiusUser]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH pw AS (
                  SELECT username, value AS password
                  FROM radcheck
                  WHERE attribute='Cleartext-Password'
                ),
                exp AS (
                  SELECT username, value AS expiration
                  FROM radcheck
                  WHERE attribute='Expiration'
                )
                SELECT u.username,
                       (pw.password IS NOT NULL) AS has_password,
                       exp.expiration
                FROM (SELECT DISTINCT username FROM radcheck) u
                LEFT JOIN pw  ON pw.username=u.username
                LEFT JOIN exp ON exp.username=u.username
                ORDER BY u.username
                """
            )
            return [RadiusUser(*row) for row in cur.fetchall()]

    def user_exists(self, username: str) -> bool:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM radcheck WHERE username=%s LIMIT 1", (username,))
            return cur.fetchone() is not None

    def upsert_radcheck(self, username: str, attribute: str, value: str, op: str = ":=") -> None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM radcheck
                WHERE username=%s AND attribute=%s
                ORDER BY id ASC
                LIMIT 1
                """,
                (username, attribute),
            )
            row = cur.fetchone()
            if row:
                (rid,) = row
                cur.execute(
                    "UPDATE radcheck SET op=%s, value=%s WHERE id=%s",
                    (op, value, rid),
                )
            else:
                cur.execute(
                    "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                    (username, attribute, op, value),
                )

    def delete_radcheck_attr(self, username: str, attribute: str) -> None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM radcheck WHERE username=%s AND attribute=%s", (username, attribute))

    def delete_user(self, username: str) -> None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM radcheck WHERE username=%s", (username,))
            cur.execute("DELETE FROM radreply WHERE username=%s", (username,))

    def get_user_details(self, username: str) -> Optional[RadiusUserDetails]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH pw AS (
                  SELECT value AS password
                  FROM radcheck
                  WHERE username=%s AND attribute='Cleartext-Password'
                  ORDER BY id ASC
                  LIMIT 1
                ),
                exp AS (
                  SELECT value AS expiration
                  FROM radcheck
                  WHERE username=%s AND attribute='Expiration'
                  ORDER BY id ASC
                  LIMIT 1
                )
                SELECT %s AS username,
                       (SELECT password FROM pw) AS password,
                       (SELECT expiration FROM exp) AS expiration
                """,
                (username, username, username),
            )
            row = cur.fetchone()
            if not row:
                return None

            # If the user doesn't exist at all (no radcheck rows), treat as None
            # (This query always returns a row; we check existence separately.)
            if not self.user_exists(username):
                return None

            return RadiusUser(username=row[0], password=row[1], expiration=row[2])
