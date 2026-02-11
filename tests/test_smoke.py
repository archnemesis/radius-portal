from radius_portal import create_app

def test_healthz():
    app = create_app()
    client = app.test_client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json["ok"] is True
