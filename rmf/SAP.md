# Security Assessment Plan (SAP)

**System:** NavyBI Prototype
**Purpose:** Defines how the controls described in [SSP.md](SSP.md) would actually be assessed. This plan has not yet been executed — see [SAR.md](SAR.md) for the current self-assessment standing in for it, and the note below on why that's not the same thing.

## 1. Purpose and scope

This SAP covers the representative control set documented in `SSP.md`, organized by the same NIST SP 800-53 Rev 5 families (AC, AU, IA, CM, SC, CA, RA, SI, PL). It does not cover the families marked "not yet applicable" in the SSP (CP, PE, PS, IR, MA, MP) — those need their own plans drafted once a real deployment makes them applicable.

## 2. Assessment methods

Per NIST SP 800-53A, each control below would be assessed using one or more of:

- **Examine** — review the actual artifact (code, config, log output, this documentation set).
- **Interview** — talk to the people who built or operate the system about how a control actually works day to day.
- **Test** — actively exercise the control (e.g., attempt a login with wrong credentials, attempt to view the governance panel as an analyst account, attempt SQL injection through the conversational query layer).

| Control | Method(s) | What "pass" looks like |
|---|---|---|
| AC-2 (Account Management) | Examine, Interview | `auth/users.json` structure reviewed; confirms only the two documented demo accounts exist and no undocumented accounts were added. |
| AC-3 (Access Enforcement) | Test | Log in as `analyst`; confirm "Data quality & governance" and "Audit log" pages are not visible or reachable, including by direct navigation attempts. |
| AC-7 (Unsuccessful Logon Attempts) | Test | Attempt repeated wrong-password logins; confirm whether (currently: whether NOT) an account lockout occurs. Expected current result: **fails** — no lockout implemented (see SSP.md). |
| AU-2 / AU-3 (Event Logging / Content) | Examine, Test | Submit a conversational query, then examine `data/audit_log.csv` for a matching row with correct username, timestamp, question, and interpreter. |
| AU-9 (Protection of Audit Information) | Examine | Confirm whether the audit log file has any access control beyond default filesystem permissions. Expected current result: **fails** — none implemented. |
| IA-2 (Identification and Authentication) | Examine, Interview | Confirm authentication mechanism is username/password only; confirm absence of MFA/PKI integration. Expected current result: **partial** — functional login exists, but not to DoD identity standards. |
| IA-5 (Authenticator Management) | Examine | Confirm password storage uses bcrypt (not plaintext or reversible encryption) by reviewing `auth/seed_users.py` and `auth/auth.py`. |
| CM-2 (Baseline Configuration) | Examine | Confirm git history exists and `requirements.txt` pins versions. |
| SC-8 (Transmission Confidentiality) | Test | Capture network traffic (e.g., via a local proxy) during an LLM-interpreted query; confirm the OpenRouter leg is TLS-encrypted and the local Streamlit UI is not. |
| SC-13 (Cryptographic Protection) | Examine | Confirm bcrypt usage for passwords; confirm absence of encryption-at-rest for the DuckDB file and CSV data. |
| CA-3 (Information Exchange) | Examine | Confirm absence of a signed Interconnection Security Agreement for the OpenRouter connection. Expected current result: **fails** — none exists. |
| RA-5 (Vulnerability Monitoring) | Test | Run a dependency vulnerability scanner (e.g., `pip-audit`) against `requirements.txt` and record findings — not yet run as of this SAP's writing. |
| SI-10 (Input Validation) | Examine, Test | Review `app/nl_query.py` and `app/llm_interpret.py` for parameterized queries; attempt a SQL-injection-style question (e.g., a unit name containing `'; DROP TABLE`) through the "Ask a question" page and confirm it does not execute as SQL. |

## 3. Assessment team

**Not yet assigned.** RMF requires assessor independence from the development team for a real ATO — the same person who built this system should not be the one certifying it's secure. This SAP is written so that an actual independent assessor (a security control assessor, SCA) could execute it directly; it should not be executed by the developer as a substitute for independent assessment.

## 4. Rules of engagement

- All testing should occur against the synthetic-data build only, using the demo accounts in `auth/users.json` — never against real data, since none exists in this environment.
- Any active testing (e.g., injection attempts, brute-force login attempts) should be run against a local instance, not a shared or exposed one.
- Findings should be recorded in [SAR.md](SAR.md)'s findings table, in the same format as the preliminary self-assessment already there, so the two can be diffed directly.

## 5. Schedule

**Not yet scheduled.** This SAP exists so a schedule can be built against it once an SCA and an AO (or AO designated representative) are identified for this system — neither exists yet for a solo prototype.
