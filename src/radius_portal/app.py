from __future__ import annotations

from flask import Flask

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

    return app
