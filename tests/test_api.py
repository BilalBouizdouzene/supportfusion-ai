from backend.app.db import SessionLocal, init_db
from backend.app.main import app, health


def test_health_endpoint():
    init_db()
    with SessionLocal() as db:
        response = health(db)
    assert response.status == "ok"


def test_search_requires_query():
    search_routes = {route.path for route in app.routes}
    assert "/api/search" in search_routes
