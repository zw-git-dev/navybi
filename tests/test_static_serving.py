"""
Production-mode tests: when frontend/dist exists, the same process that
serves the API also serves the SPA.

These skip when the frontend hasn't been built -- which is the normal state
during development (Vite serves the SPA instead) and in CI's backend job,
where the frontend is built in a separate job. Skipping rather than failing
keeps the suite honest about what it actually verified.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

pytestmark = pytest.mark.skipif(
    not os.path.isdir(DIST),
    reason="frontend/dist not built (run: cd frontend && npm run build)",
)


@pytest.fixture
def client():
    from api.main import app
    with TestClient(app) as c:
        yield c


def test_root_serves_the_spa_shell(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.parametrize("route", ["/trends", "/ask", "/governance", "/audit-log"])
def test_client_side_routes_serve_the_shell_on_a_hard_refresh(client, route):
    """
    Client-side routing means the server never has a real file at these
    paths. Without the catch-all, refreshing the page or opening a shared
    deep link would 404 -- a classic SPA deployment bug that only shows up
    outside the dev server.
    """
    r = client.get(route)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_api_routes_are_not_shadowed_by_the_catch_all(client):
    """
    The catch-all is registered last so it can't intercept API routes. If
    that ordering ever breaks, this endpoint would start returning the HTML
    shell with a 200 instead of an honest 401.
    """
    r = client.get("/api/dashboard/overview")
    assert r.status_code == 401
    assert "application/json" in r.headers["content-type"]


def test_unknown_api_path_returns_json_not_html(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert "application/json" in r.headers["content-type"]
