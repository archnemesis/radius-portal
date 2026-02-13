from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from psycopg_pool import ConnectionPool


@dataclass(frozen=True)
class RadiusUser:
    username: str
    password: Optional[str]
    expiration: Optional[str]


@dataclass(frozen=True)
class UserMeta:
    username: str
    created_at: str
    created_by: str
    updated_at: str
    updated_by: str
    note: Optional[str]


@dataclass(frozen=True)
class AuditEvent:
    occurred_at: str
    actor: str
    action: str
    target_username: Optional[str]
    detail: dict[str, key]


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

    def upsert_user_meta_on_create(self, username: str, actor: str, note: str | None = None) -> None:
        """
        Create user_meta row if missing; if it exists, only update updated_* (do NOT clobber created_*).
        """
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO portal.user_meta (username, created_by, updated_by, note)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE
                  SET updated_at = now(),
                      updated_by = EXCLUDED.updated_by,
                      note = COALESCE(EXCLUDED.note, portal.user_meta.note)
                """,
                (username, actor, actor, note),
            )

    def touch_user_meta(self, username: str, actor: str) -> None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE portal.user_meta
                   SET updated_at = now(),
                       updated_by = %s
                 WHERE username = %s
                """,
                (actor, username),
            )

    def get_user_meta(self, username: str) -> Optional[UserMeta]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT username, created_at::text, created_by, updated_at::text, updated_by, note
                  FROM portal.user_meta
                 WHERE username = %s
                """,
                (username,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return UserMeta(*row)

    def insert_audit_event(
        self,
        actor: str,
        action: str,
        target_username: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        detail = detail or {}
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO portal.audit_log (actor, action, target_username, detail)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (actor, action, target_username, json.dumps(detail)),
            )

    def list_audit_events(self, target_username: str, limit: int = 25) -> list[AuditEvent]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT occurred_at::text, actor, action, target_username, detail
                  FROM portal.audit_log
                 WHERE target_username = %s
                 ORDER BY occurred_at DESC
                 LIMIT %s
                """,
                (target_username, limit),
            )
            rows = cur.fetchall()
            out: list[AuditEvent] = []
            for occurred_at, actor, action, target, detail in rows:
                out.append(AuditEvent(occurred_at, actor, action, target, detail or {}))
            return out

