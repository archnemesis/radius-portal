CREATE SCHEMA IF NOT EXISTS portal;

CREATE TABLE IF NOT EXISTS portal.user_meta (
  username        text PRIMARY KEY,
  created_at      timestamptz NOT NULL DEFAULT now(),
  created_by      text NOT NULL,
  updated_at      timestamptz NOT NULL DEFAULT now(),
  updated_by      text NOT NULL,
  note            text
);

CREATE TABLE IF NOT EXISTS portal.audit_log (
  id              bigserial PRIMARY KEY,
  occurred_at     timestamptz NOT NULL DEFAULT now(),
  actor           text NOT NULL,          -- who did it (IPA user)
  action          text NOT NULL,          -- CREATE_USER / SET_PASSWORD / DELETE_USER ...
  target_username text,
  detail          jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS audit_log_actor_idx ON portal.audit_log(actor);
CREATE INDEX IF NOT EXISTS audit_log_target_idx ON portal.audit_log(target_username);

