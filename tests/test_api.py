"""
API-layer tests: authentication, role-based access control, and the response
contracts the frontend depends on.

The access-control tests here matter more than their line count suggests.
The SPA hides admin navigation and redirects admin routes, but that's a UI
convenience -- the actual enforcement has to be server-side, or anyone who
can send an HTTP request bypasses it entirely. rmf/SSP.md's AC-3 entry
claims exactly that enforcement exists; these tests are what keep that
claim true as the code changes.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from tests.conftest import ADMIN, ANALYST

ADMIN_ONLY_ENDPOINTS = [
    "/api/governance/cleansing-log",
    "/api/governance/row-counts",
    "/api/governance/measures",
    "/api/audit-log",
]

AUTHENTICATED_ENDPOINTS = [
    "/api/dashboard/overview",
    "/api/dashboard/trends",
    "/api/dashboard/map",
    "/api/dashboard/drilldown",
    "/api/ask/meta",
] + ADMIN_ONLY_ENDPOINTS


# --- health and auth ---------------------------------------------------


def test_health_needs_no_auth(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_login_returns_user_without_leaking_password_hash(client):
    r = client.post("/api/auth/login", json=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body == {"username": "admin", "role": "admin", "display_name": "Demo Administrator"}
    # The user record in users.json carries a bcrypt hash; it must not ride
    # along in the login response just because it's on the same object.
    assert "password_hash" not in body


def test_login_sets_httponly_session_cookie(client):
    r = client.post("/api/auth/login", json=ADMIN)
    cookie_header = r.headers.get("set-cookie", "")
    assert "navybi_session=" in cookie_header
    # httponly keeps the token out of reach of page JavaScript, which is the
    # reason for using a cookie here rather than handing a token to the SPA.
    assert "httponly" in cookie_header.lower()


def test_login_rejects_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_rejects_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "whatever"})
    assert r.status_code == 401


def test_me_requires_authentication(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_current_user(admin_client):
    r = admin_client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_logout_ends_the_session(admin_client):
    assert admin_client.get("/api/auth/me").status_code == 200
    assert admin_client.post("/api/auth/logout").status_code == 200
    assert admin_client.get("/api/auth/me").status_code == 401


def test_tampered_token_is_rejected(client):
    """
    A forged or corrupted token must fail signature verification rather than
    being taken at face value -- the cookie is the only thing standing
    between a caller and an admin session.

    Note the explicit clear(): httpx's cookie jar appends rather than
    replaces, so setting a bad cookie on top of a good one sends both and
    the server happily reads the valid one. The client has to present the
    bogus token *alone* for this test to mean anything.
    """
    client.post("/api/auth/login", json=ADMIN)
    client.cookies.clear()
    client.cookies.set("navybi_session", "not.a.valid.jwt")
    assert client.get("/api/auth/me").status_code == 401


def test_token_signed_with_a_different_secret_is_rejected(client):
    """
    Guards the actual signature check, not just malformed-string handling:
    a structurally perfect token minted with the wrong key must still fail.
    """
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    forged = pyjwt.encode(
        {
            "sub": "admin",
            "role": "admin",
            "display_name": "Demo Administrator",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        "not-the-real-signing-secret",
        algorithm="HS256",
    )
    client.cookies.clear()
    client.cookies.set("navybi_session", forged)
    assert client.get("/api/auth/me").status_code == 401


def test_expired_token_is_rejected(client):
    from datetime import datetime, timedelta, timezone

    import jwt as pyjwt

    from api.deps import JWT_ALGORITHM, JWT_SECRET

    expired = pyjwt.encode(
        {
            "sub": "admin",
            "role": "admin",
            "display_name": "Demo Administrator",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.clear()
    client.cookies.set("navybi_session", expired)
    assert client.get("/api/auth/me").status_code == 401


def test_an_analyst_cannot_forge_an_admin_role(client):
    """
    The role comes out of the signed payload, so an analyst can't escalate by
    editing it -- but that only holds because the signature is verified. This
    pins the property explicitly, since role escalation is the concrete harm
    AC-3 is protecting against.
    """
    import json
    import base64

    r = client.post("/api/auth/login", json=ANALYST)
    token = r.cookies["navybi_session"]
    header_b64, payload_b64, sig = token.split(".")

    def _b64d(s):
        return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

    payload = json.loads(_b64d(payload_b64))
    payload["role"] = "admin"
    tampered_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()

    client.cookies.clear()
    client.cookies.set("navybi_session", f"{header_b64}.{tampered_payload}.{sig}")
    assert client.get("/api/governance/measures").status_code == 401


# --- access control ---------------------------------------------------


@pytest.mark.parametrize("endpoint", AUTHENTICATED_ENDPOINTS)
def test_endpoints_reject_unauthenticated_callers(client, endpoint):
    assert client.get(endpoint).status_code == 401


@pytest.mark.parametrize("endpoint", ADMIN_ONLY_ENDPOINTS)
def test_admin_endpoints_reject_analysts(analyst_client, endpoint):
    """
    The decisive test for AC-3: an analyst holding a perfectly valid session
    must still be refused these endpoints server-side, regardless of what
    the SPA chooses to render.
    """
    assert analyst_client.get(endpoint).status_code == 403


@pytest.mark.parametrize("endpoint", ADMIN_ONLY_ENDPOINTS)
def test_admin_endpoints_allow_admins(admin_client, endpoint):
    assert admin_client.get(endpoint).status_code == 200


def test_ask_rejects_unauthenticated_callers(client):
    assert client.post("/api/ask", json={"question": "anything"}).status_code == 401


# --- dashboard response contracts -------------------------------------


def test_overview_returns_kpis_and_all_chart_series(admin_client):
    r = admin_client.get("/api/dashboard/overview")
    assert r.status_code == 200
    body = r.json()

    for kpi in (
        "total_missions",
        "overall_completion_pct",
        "overall_readiness_pct",
        "overall_training_currency_pct",
    ):
        assert body["kpis"][kpi] is not None, f"{kpi} should not be null"

    for series in (
        "completion_by_unit",
        "readiness_by_unit",
        "training_by_unit",
        "downtime_by_equipment",
        "resolution_by_unit",
    ):
        assert len(body[series]) > 0, f"{series} came back empty"

    # The frontend reads these exact keys off the records; renaming a column
    # in measures.sql without updating the SPA would break the chart
    # silently (axes render, bars don't), so pin the contract here.
    assert {"unit_name", "completion_rate_pct"} <= set(body["completion_by_unit"][0])
    assert {"equipment_type", "avg_downtime_hours"} <= set(body["downtime_by_equipment"][0])


def test_trends_returns_units_and_series(admin_client):
    body = admin_client.get("/api/dashboard/trends").json()
    assert len(body["units"]) > 0
    assert {"unit_name", "mission_month", "mission_count"} <= set(body["mission_count_by_month"][0])
    assert {"mission_type", "avg_duration_hours"} <= set(body["avg_duration_by_type"][0])


def test_map_returns_plottable_coordinates(admin_client):
    body = admin_client.get("/api/dashboard/map").json()
    assert len(body["statuses"]) > 0
    mission = body["missions"][0]
    assert {"mission_lat", "mission_lon", "status"} <= set(mission)
    assert mission["mission_lat"] is not None and mission["mission_lon"] is not None


def test_drilldown_returns_rows_and_filter_options(admin_client):
    body = admin_client.get("/api/dashboard/drilldown").json()
    assert len(body["units"]) > 0
    assert len(body["missions"]) > 0


def test_json_has_no_nan_tokens(admin_client):
    """
    pandas NaN serializes to a bare `NaN` literal, which is invalid JSON and
    makes a strict JSON.parse() on the frontend throw. api/utils.py converts
    those to null; this guards that conversion, since the dataset
    deliberately contains missing values (missing durations, etc.).
    """
    raw = admin_client.get("/api/dashboard/map").text
    assert "NaN" not in raw
    assert "Infinity" not in raw


# --- the ask endpoint -------------------------------------------------


def test_ask_meta_lists_sample_questions(admin_client):
    body = admin_client.get("/api/ask/meta").json()
    assert len(body["sample_questions"]) > 0
    assert isinstance(body["llm_configured"], bool)


def test_ask_answers_a_supported_question(admin_client, keyword_only):
    r = admin_client.post("/api/ask", json={"question": "What is the mission completion rate by unit?"})
    assert r.status_code == 200
    body = r.json()

    assert body["understood"] is True
    assert body["sql"], "an answer must carry the SQL that produced it"
    assert len(body["df"]) > 0
    # The chart spec is the contract the SPA renders from -- it names columns
    # rather than shipping a rendered figure (see PLAN.md section 4.9).
    assert body["chart"]["kind"] in ("bar", "line")
    assert body["chart"]["x"] in body["df"][0]
    assert body["chart"]["y"] in body["df"][0]
    assert body["measure_description"], "explainability depends on this being populated"


def test_ask_reports_an_unsupported_question_honestly(admin_client, keyword_only):
    """
    A confident-looking answer to a question outside the semantic layer is
    the failure mode this project spent seven rounds closing (see
    QUESTION_TEST_LOG.md). The endpoint must say it didn't understand
    rather than returning a plausible chart.
    """
    body = admin_client.post("/api/ask", json={"question": "What is the weather forecast for tomorrow?"}).json()
    assert body["understood"] is False
    assert body["chart"] is None


def test_ask_logs_every_request_including_cache_hits(admin_client, keyword_only):
    """
    Caching may skip recomputing an answer, but it must never skip the audit
    trail -- 'who asked what, when' is a governance claim
    (GOVERNANCE_NOTES.md, rmf/SSP.md AU controls), not a performance detail.
    """
    question = "What is the mission completion rate by unit?"
    before = len(admin_client.get("/api/audit-log").json())

    admin_client.post("/api/ask", json={"question": question})
    admin_client.post("/api/ask", json={"question": question})  # served from cache

    after = admin_client.get("/api/audit-log").json()
    assert len(after) == before + 2, "both the fresh and cached request should be logged"
    assert after[0]["question"] == question
    assert after[0]["username"] == "admin"


def test_ask_cache_is_case_and_whitespace_insensitive(admin_client, keyword_only):
    from api.routers import ask

    admin_client.post("/api/ask", json={"question": "What is the mission completion rate by unit?"})
    assert len(ask._ask_cache) == 1

    admin_client.post("/api/ask", json={"question": "  WHAT IS THE MISSION COMPLETION RATE BY UNIT?  "})
    assert len(ask._ask_cache) == 1, "trivial phrasing differences shouldn't cost a second LLM call"


def test_ask_rejects_a_malformed_body(admin_client):
    assert admin_client.post("/api/ask", json={}).status_code == 422


# --- governance contracts ---------------------------------------------


def test_row_counts_cover_all_three_source_formats(admin_client):
    """
    Three heterogeneous ingestion paths (CSV, JSON, SQLite) is a specific
    claim this prototype makes; the governance panel is where it's evidenced.
    """
    rows = admin_client.get("/api/governance/row-counts").json()
    assert {r["source_format"] for r in rows} == {"CSV", "JSON", "SQLite"}
    assert all(r["raw_row_count"] > 0 for r in rows)


def test_every_measure_carries_a_description_and_dax(admin_client):
    """
    warehouse/semantic_layer.py's docstring states a measure without both a
    plain-language description and a DAX equivalent isn't demo- or
    migration-ready. This is that rule, enforced.
    """
    measures = admin_client.get("/api/governance/measures").json()
    assert len(measures) > 0
    for m in measures:
        assert m["description"].strip(), f"{m['id']} has no description"
        assert m["dax"].strip(), f"{m['id']} has no DAX equivalent"


def test_cleansing_log_is_populated(admin_client):
    log = admin_client.get("/api/governance/cleansing-log").json()
    assert len(log) > 0
    assert {"table", "action", "reason"} <= set(log[0])
