from __future__ import annotations

from flask import Flask
from flask import g, request, abort

from .config import Config
from .db.pool import make_pool
from .db.radius_repo import RadiusRepo
from .routes.users import bp as users_bp


def create_app(cfg: Config | None = None) -> Flask:
    cfg = cfg or Config()
    app = Flask(__name__)
    app.secret_key = cfg.app_secret

    pool = make_pool(cfg)
    repo = RadiusRepo(pool)

    app.extensions["db_pool"] = pool
    app.extensions["radius_repo"] = repo

    app.register_blueprint(users_bp)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    # inside create_app(), after app creation:
    @app.before_request
    def load_remote_user():
        # Only trust this header because Apache sets it and strips client-sent ones.
        remote_user = request.headers.get("X-Remote-User")
        if not remote_user:
            # If Apache is configured with Require valid-user, this normally won't happen.
            abort(401)

        if "@" in remote_user:
            remote_user = remote_user.split("@")[0]

        g.remote_user = remote_user
        print("config object: %s" % dir(cfg))
        g.admins = set(cfg.admin_users)

    @app.context_processor
    def inject_config():
        return {"cfg": cfg}

    @app.context_processor
    def inject_user():
        from flask import g
        return dict(current_user=getattr(g, "remote_user", None))

    return app
