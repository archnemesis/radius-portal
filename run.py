from radius_portal import create_app
from radius_portal.config import Config

cfg = Config
app = create_app(cfg)
app.run(host=cfg.flask_host, port=cfg.flask_port, debug=cfg.flask_debug)
