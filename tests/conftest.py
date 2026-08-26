"""
Shared fixtures for the API tests.

These tests exercise the real FastAPI app against the real DuckDB warehouse
and the real seeded users.json -- not mocks. That's deliberate: the whole
point of the API layer is that it wires auth, role checks, the semantic
layer, and the NL interpreters together correctly, and a test suite built
on mocked-out internals would pass while that wiring is broken. The
prerequisites (generated data, built warehouse, seeded users) are the same
ones `./run.sh` sets up, so if the app runs locally these tests run too;
`pytest.skip` below explains the fix rather than failing cryptically if
they're missing.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

WAREHOUSE_PATH = os.path.join(os.path.dirname(__file__), "..", "warehouse", "navybi.duckdb")
USERS_PATH = os.path.join(os.path.dirname(__file__), "..", "auth", "users.json")

ADMIN = {"username": "admin", "password": "ChangeMe!Admin1"}
ANALYST = {"username": "analyst", "password": "ChangeMe!Analyst1"}


def pytest_collection_modifyitems(config, items):
    """Skip the whole API suite with an actionable message if setup is missing."""
    missing = []
    if not os.path.exists(WAREHOUSE_PATH):
        missing.append("warehouse/navybi.duckdb (run: python3 warehouse/semantic_layer.py)")
    if not os.path.exists(USERS_PATH):
        missing.append("auth/users.json (run: python3 auth/seed_users.py)")
    if missing:
        skip = pytest.mark.skip(reason="Missing test prerequisites: " + "; ".join(missing))
        for item in items:
            if "api" in str(item.fspath):
                item.add_marker(skip)


@pytest.fixture
def client():
    from api.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clear_ask_cache():
    """
    The /api/ask TTL cache is module-level state shared across requests, so
    without clearing it a test asserting "this question triggers a fresh
    interpretation" could silently pass on another test's cached answer.
    """
    from api.routers import ask
    ask._ask_cache.clear()
    yield
    ask._ask_cache.clear()


@pytest.fixture
def admin_client(client):
    r = client.post("/api/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return client


@pytest.fixture
def analyst_client(client):
    r = client.post("/api/auth/login", json=ANALYST)
    assert r.status_code == 200, r.text
    return client


@pytest.fixture
def keyword_only(monkeypatch):
    """
    Forces the deterministic keyword-matcher path by making the LLM look
    unconfigured. Without this, these tests would hit the real OpenRouter
    API whenever a key happens to be present in the environment -- making
    them slow, network-dependent, and liable to fail on rate limits rather
    than on actual regressions. LLM-vs-keyword interpretation quality is
    tracked separately in tests/test_questions.py and QUESTION_TEST_LOG.md;
    what these tests check is the API contract around whichever interpreter
    answered.
    """
    from app import llm_interpret
    monkeypatch.setattr(llm_interpret, "is_configured", lambda: False)
