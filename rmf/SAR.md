# Security Assessment Report (SAR)

**System:** NavyBI Prototype
**Assessment type:** **Preliminary developer self-assessment.** This is explicitly NOT an independent security control assessment. A real SAR is produced by an independent assessor (an SCA) executing the procedures in [SAP.md](SAP.md) — this document exists so there's a findings-report *template and a real starting draft* to hand to one, not to substitute for that review.
**Assessed against:** The representative control set in [SSP.md](SSP.md).
**Assessment date:** See git history for this file's commit date.

## Executive summary

Of the controls examined, most sit at **Partial** implementation — real, working functionality exists but falls short of what a production DoD system would need. Two findings stand out as materially more significant than the rest and are called out first:

1. **No DoD PKI/CAC authentication (IA-2).** The system has real, working login (unlike having none at all), but username/password accounts are not an acceptable identity mechanism for a real DoD system. This is an organizational/infrastructure decision, not something fixable by more application code alone.
2. **Unmanaged third-party LLM interconnection (SC/CA).** Every LLM-interpreted question sends data to OpenRouter, a commercial API, with no data-handling agreement or confirmed authorization boundary. Harmless today (synthetic data only) but blocking for any real deployment until resolved.

Neither finding is a surprise buried in this report — both are already named plainly in [GOVERNANCE_NOTES.md](../GOVERNANCE_NOTES.md) and [SSP.md](SSP.md), because this project's standing practice (see [QUESTION_TEST_LOG.md](../QUESTION_TEST_LOG.md)'s seven rounds) is to name real gaps as they're found rather than let a report be the first place they surface.

## Findings

| # | Control | Finding | Severity | Recommendation |
|---|---|---|---|---|
| 1 | IA-2 | Authentication is local username/password only; no MFA, no DoD PKI/CAC integration. | **High** (for any real deployment; N/A-severity for the current synthetic-data demo) | Integrate with an approved DoD identity provider before any real data is connected. Do not treat this as an application-layer fix — it requires organizational/infrastructure support. |
| 2 | SC-8 / CA-3 | LLM queries are sent to a third-party commercial API (OpenRouter) with no data-handling agreement, no TLS on the local web app, and no confirmed authorization boundary for the upstream model provider. | **High** (for real data; **Informational** for the current synthetic-data demo) | Resolve the LLM hosting/data-exposure decision flagged in `GOVERNANCE_NOTES.md` before connecting real data — options include an on-prem/self-hosted model, a FedRAMP-authorized hosting arrangement, or explicit risk acceptance by the data/system owner. |
| 3 | AU-9 / AU-11 | The audit log (`data/audit_log.csv`) has no access control beyond filesystem permissions, no tamper-evidence, and no retention/rotation policy. | Moderate | Move audit logging to a protected, append-only store with a defined retention policy before any real deployment. |
| 4 | AC-7 | No account lockout after repeated failed login attempts. | Moderate | Add attempt-count tracking and temporary lockout to `auth/auth.py`. |
| 5 | AC-3 | Role-based access controls page visibility (admin vs. analyst) but not data-row visibility — any authenticated user can query every unit's data. | Moderate (Low for a single-organization demo; would rise with real, multi-unit sensitive data) | Define and implement a data-level access model if this is ever used across multiple units/commands with differing access needs. |
| 6 | SC-13 | No encryption at rest for the DuckDB warehouse, CSV data, or audit log. | Moderate (for real data; Low for synthetic data) | Add encryption at rest before storing real data. |
| 7 | RA-5 | No dependency vulnerability scanning integrated into the build/test process. | Low | Add `pip-audit` or an equivalent to the development workflow. |
| 8 | CM-6 | No formal configuration hardening baseline for the host OS, Python runtime, or application server (e.g., no TLS on the app itself, default bind settings, session cookie not marked `secure`). | Low (as-built, single-host demo); Moderate (once network-exposed) | Apply a hardening checklist before any network-facing deployment. |
| 9 | CA-2 / CA-6 | No independent security assessment has occurred; no ATO has been requested or granted. | N/A as a "finding" — this is the expected state before a first assessment, named here so it's tracked rather than assumed | See [POAM.md](POAM.md) for the path to requesting one. |

## What was NOT found (explicitly checked and clear)

- **SQL injection:** entity values used in queries are validated against known vocabulary and passed as bound parameters (`app/nl_query.py`, `app/llm_interpret.py`), not raw string interpolation. Spot-checked; no injection path found in the conversational query layer.
- **Plaintext password storage:** passwords are bcrypt-hashed (`auth/seed_users.py`); the application never stores or logs a plaintext password after seeding.
- **Secrets in version control:** the OpenRouter API key lives in a gitignored `.env` file, confirmed absent from `git status` output during development (see project history). Demo user credentials in `auth/seed_users.py` are intentionally documented in plaintext in that file, since they are non-production demo accounts, not real secrets.

## Assessor's note (self-assessment caveat, stated plainly)

Every finding above was identified by the same team that built the system. That is a real limitation of this report, not a formality — a genuinely independent assessor might find things this self-assessment missed, and has no incentive to describe a finding more favorably than it deserves. Treat this SAR as a solid starting draft for an independent assessment, not as that assessment having already happened.
