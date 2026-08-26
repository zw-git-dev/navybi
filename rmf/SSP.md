# System Security Plan (SSP)

**System name:** NavyBI Prototype
**Categorization:** Low (as-built, synthetic data) / Moderate (target, real data) — see [SYSTEM_CATEGORIZATION.md](SYSTEM_CATEGORIZATION.md)
**Control baseline referenced:** NIST SP 800-53 Rev 5, representative controls from the Moderate baseline (see note below on scope)

## Scope note

This SSP does not attempt a control-by-control listing of the full ~250-control Moderate baseline — that level of completeness belongs in an actual ATO package prepared with (and reviewed by) real security engineering and assessment staff, not a solo prototype build. Instead, it covers a representative set of controls per family, prioritized toward the ones this system's own architecture actually touches, with an honest status for each: **Implemented**, **Partial**, **Planned**, or **N/A**. Every "Implemented" or "Partial" status below points at the actual file/function responsible, so this document can be checked against the code, not just trusted.

## 1. System description

NavyBI Prototype is a self-contained conversational analytics application for post-mission reporting data. See [README.md](../README.md) for the full architecture description. In brief:

- **Data pipeline:** synthetic data generation (`data/generate_synthetic_data.py`) → automated cleansing (`pipeline/clean.py`) → a governed semantic layer in DuckDB (`warehouse/`).
- **Application:** a FastAPI backend (`api/`) serving a React/TypeScript single-page app (`frontend/`), presenting dashboards, a conversational query interface, and (for admins) governance/audit views.
- **Authentication:** local username/password accounts (`auth/`), two roles (admin, analyst); sessions carried as a signed JWT in an httpOnly cookie (`api/deps.py`).
- **External interconnection:** the conversational query layer calls an LLM via OpenRouter (`app/llm_interpret.py`) over HTTPS when configured, with a local keyword-matching fallback when it isn't.
- **Deployment (as-built):** runs on a single host (a developer laptop in this build), accessed via `localhost`, no network exposure beyond the outbound OpenRouter API call.

## 2. System boundary

```
                     ┌───────────────────────────────────────────┐
                     │           NavyBI Prototype (single host)    │
                     │                                              │
  Browser  ──HTTP──▶ │  React SPA (frontend/)                       │
  (localhost)        │        │  fetch /api/*                        │
                     │        ▼                                     │
                     │  FastAPI app (api/) ──▶ DuckDB warehouse     │
                     │        │                    (warehouse/)     │
                     │        ▼                                     │
                     │  auth/ (local accounts, audit log)            │
                     └────────┼───────────────────────────────────┘
                              │ HTTPS (question text + entity vocabulary)
                              ▼
                    OpenRouter API (third-party, external)
                              │
                              ▼
                    Upstream model provider (varies by model)
```

The OpenRouter connection is the system's only external network interconnection and is treated as a distinct boundary-crossing point throughout this document (see SC and CA sections below) — this is also called out plainly in [GOVERNANCE_NOTES.md](../GOVERNANCE_NOTES.md)'s Governable section.

## 3. Control implementation status

### AC — Access Control

| Control | Status | Detail |
|---|---|---|
| AC-2 Account Management | Partial | Two demo accounts seeded by `auth/seed_users.py`. No self-service provisioning, no periodic account review, no deprovisioning workflow. Real deployment needs accounts tied to an authoritative personnel/identity source. |
| AC-3 Access Enforcement | Partial | Role-based access enforced server-side in `api/deps.py::require_admin` (built on `auth.has_governance_access()`), which returns HTTP 403 to non-admin callers on the governance and audit-log endpoints; the SPA additionally hides admin navigation and redirects admin routes (`frontend/src/ProtectedRoute.tsx`). Enforcement is deliberately server-side as well as client-side, since a client-side-only guard is a UI convenience and not access control — verified by calling the endpoints directly as an analyst and receiving 403. Gap: no row-level/data-level access control (e.g., unit-level compartmentalization) — any authenticated user can query data for every unit. |
| AC-7 Unsuccessful Logon Attempts | Not implemented | `auth/auth.py` has no failed-attempt counter or account lockout. POA&M item. |
| AC-8 System Use Notification | Not implemented | No warning banner on login. POA&M item — trivial to add, not yet done. |
| AC-17 Remote Access | N/A (as-built) | System runs on `localhost` only; no remote access path exists to control. Becomes applicable the moment this is deployed off a single host. |

### AU — Audit and Accountability

| Control | Status | Detail |
|---|---|---|
| AU-2 Event Logging | Partial | `auth.log_query()` logs every conversational query: who, when, what was asked, which interpreter answered, whether it was understood, how many caveats fired. Visible to admins via the in-app Audit Log page. Gap: login/logout events and dashboard page views are not logged, only conversational queries. |
| AU-3 Content of Audit Records | Partial | Records include timestamp (UTC), username, role, question text, understood flag, interpreter, and caveat count. No source IP or session identifier is captured. |
| AU-9 Protection of Audit Information | Not implemented | The audit log (`data/audit_log.csv`) has ordinary filesystem permissions only — no access control separate from the rest of the filesystem, no tamper-evidence (e.g., hash chaining or write-once storage). |
| AU-11 Audit Record Retention | Not implemented | No retention or rotation policy; the log file grows unbounded. |

### IA — Identification and Authentication

| Control | Status | Detail |
|---|---|---|
| IA-2 Identification and Authentication (Organizational Users) | Partial | Username/password login is real and functional (`auth/auth.py::verify_credentials`, `api/routers/auth.py::login`), with sessions carried as a signed JWT in an httpOnly cookie (`api/deps.py`). **This is the single largest gap for any real DoD deployment**: no multi-factor authentication, and critically, no DoD PKI/CAC integration, which is a hard requirement for real DoD systems, not an optional hardening step. |
| IA-5 Authenticator Management | Partial | Passwords are bcrypt-hashed at rest (`auth/seed_users.py`), never stored or logged in plaintext by the application. Gap: no complexity policy enforcement, no expiration/rotation, no self-service reset. The two demo passwords are documented in plaintext in `auth/seed_users.py` itself — acceptable only because these are non-production demo accounts for a synthetic-data prototype, and is called out explicitly in that file's docstring. |

### CM — Configuration Management

| Control | Status | Detail |
|---|---|---|
| CM-2 Baseline Configuration | Implemented | The entire system is version-controlled in git; `requirements.txt` pins exact dependency versions. |
| CM-6 Configuration Settings | Not implemented | No formal hardening baseline applied to the host OS, Python runtime, or the application server's own configuration (e.g., default bind address, no TLS on the Uvicorn/FastAPI server itself). Note: the JWT signing secret is not a committed default — absent an explicit `JWT_SECRET`, `api/deps.py` generates a random per-process secret at startup, so no known signing key ships in the repository. |

### SC — System and Communications Protection

| Control | Status | Detail |
|---|---|---|
| SC-7 Boundary Protection | N/A (as-built) | Single host, no defined network boundary to protect. Real deployment requires a defined enclave boundary and network controls. |
| SC-8 Transmission Confidentiality and Integrity | Partial | The OpenRouter leg is HTTPS (TLS, via the `requests` library) — that traffic is encrypted in transit. The local web app itself (Uvicorn/FastAPI, and the Vite dev server in development) is served over plain HTTP with no TLS termination configured. Real deployment requires TLS in front of the web app. Session cookies are set `httponly` with `samesite=lax` (`api/routers/auth.py`), but deliberately not `secure`, since that flag would break the plain-HTTP localhost demo — enabling it is a required step for any TLS deployment. |
| SC-13 Cryptographic Protection | Partial | bcrypt is used for password hashing (appropriate, one-way). No encryption at rest for the DuckDB warehouse file, CSV data, or the audit log. |
| **SC-related finding: unmanaged external interconnection** | **Not implemented / open risk** | Every LLM-interpreted query sends the question text and the full known entity vocabulary (unit names, mission types, equipment types, certifications) to OpenRouter, a third-party commercial API, with no data-handling agreement, no confirmed FedRAMP authorization for the serving infrastructure, and no on-prem/air-gapped alternative configured. Harmless today because the data is synthetic; **this is the control gap that would block real data from ever reaching this connection** without a resolved hosting decision. Documented in depth in [GOVERNANCE_NOTES.md](../GOVERNANCE_NOTES.md)'s Governable section. |

### CA — Assessment, Authorization, and Monitoring

| Control | Status | Detail |
|---|---|---|
| CA-2 Control Assessments | Not started | This SSP and the accompanying [SAR.md](SAR.md) constitute a developer self-assessment, explicitly not an independent assessment. See [SAP.md](SAP.md) for what an actual assessment would need to cover. |
| CA-3 Information Exchange | Not implemented | No Interconnection Security Agreement (ISA) or equivalent exists for the OpenRouter connection described above. |
| CA-6 Authorization | Not granted | No ATO has been requested from, or granted by, an actual Authorizing Official. See [POAM.md](POAM.md) and the ATO path memo in that same document. |

### RA — Risk Assessment

| Control | Status | Detail |
|---|---|---|
| RA-3 Risk Assessment | Partial | The seven rounds of adversarial testing documented in [QUESTION_TEST_LOG.md](../QUESTION_TEST_LOG.md) constitute real, evidence-based risk identification for the conversational layer specifically — an unusually thorough record for a prototype. This is not, however, a formal organizational risk assessment covering the whole system. |
| RA-5 Vulnerability Monitoring and Scanning | Not implemented | Dependencies are version-pinned (`requirements.txt`) but not scanned for known vulnerabilities (e.g., no `pip-audit` or equivalent integrated). |

### SI — System and Information Integrity

| Control | Status | Detail |
|---|---|---|
| SI-2 Flaw Remediation | Partial | Real, documented flaw-remediation history exists — see [QUESTION_TEST_LOG.md](../QUESTION_TEST_LOG.md)'s seven rounds, each finding and fixing genuine bugs (including a crash-class bug in round 6). This is ad hoc testing-driven remediation, not a formal vulnerability/patch management process with SLAs. |
| SI-10 Information Input Validation | Partial | Entity values used in SQL queries are validated against a known vocabulary and passed as bound parameters, never raw string interpolation (`app/nl_query.py`, `app/llm_interpret.py`) — a deliberate injection-safety design choice made from the start. Broader input validation (question-length limits, encoding checks) is not formalized. |

### PL — Planning

| Control | Status | Detail |
|---|---|---|
| PL-2 System Security and Privacy Plans | Implemented | This document. |

### Not yet applicable at prototype stage (explicitly out of scope, not silently ignored)

| Family | Why it's not covered here |
|---|---|
| CP — Contingency Planning | No production data exists to back up or recover; a real deployment needs a backup/recovery/continuity plan before it holds real data. |
| PE — Physical and Environmental Protection | Runs on a developer workstation; not applicable until deployed to a real hosting environment with a physical security posture to describe. |
| PS — Personnel Security | No personnel security process exists for a 2-account demo; applicable once real users/accounts are provisioned. |
| IR — Incident Response | No incident response plan exists. Needed before any real deployment. |
| MA — Maintenance / MP — Media Protection | Not applicable to a local prototype with no removable media or formal maintenance process. |

## 4. Summary

The pattern across this whole control review matches the pattern the rest of this project's documentation already established (see [QUESTION_TEST_LOG.md](../QUESTION_TEST_LOG.md) and [GOVERNANCE_NOTES.md](../GOVERNANCE_NOTES.md)): be specific about what's real, don't round partial credit up to "done," and point at the actual code or actual gap rather than asserting either. The two largest, most consequential gaps for any real deployment are **IA-2 (no DoD PKI/CAC)** and the **unmanaged OpenRouter interconnection** — both need an actual organizational decision, not more solo engineering, before real data could responsibly reach this system. See [POAM.md](POAM.md) for the full prioritized list.
