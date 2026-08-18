# Plan of Action & Milestones (POA&M)

**System:** NavyBI Prototype
**Source:** Findings in [SAR.md](SAR.md), cross-referenced to [SSP.md](SSP.md) control status.

Every row below needs a real responsible party and a real target date before this is an actual POA&M — those are placeholders here because a solo development effort has neither an assigned ISSO/ISSM nor a program schedule to draw dates from. The point of populating it now, with real weaknesses and real recommended actions, is that a program picking this up doesn't start from a blank template.

| # | Weakness | Source | Risk | Corrective action | Resources needed | Responsible party | Target date | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | No DoD PKI/CAC authentication | SAR #1, SSP IA-2 | High (real deployment) | Integrate an approved DoD identity provider / CAC authentication in place of local accounts | Access to a DoD IdP or PKI infrastructure; not solvable by application code alone | TBD (needs org sponsor) | TBD | Open |
| 2 | Unmanaged third-party LLM interconnection (OpenRouter) | SAR #2, SSP SC/CA | High (real deployment) | Resolve LLM hosting decision: on-prem model, FedRAMP-authorized hosting, or explicit documented risk acceptance | A security/data-governance decision from whoever owns real post-mission data | TBD (needs Information Owner) | TBD | Open |
| 3 | Audit log has no access control, tamper-evidence, or retention policy | SAR #3, SSP AU-9/AU-11 | Moderate | Move audit log to a protected, append-only store with defined retention | Engineering time; a decision on retention duration from records-management guidance | TBD | TBD | Open |
| 4 | No account lockout on repeated failed logins | SAR #4, SSP AC-7 | Moderate | Add attempt-count tracking and temporary lockout to `auth/auth.py` | Engineering time (small) | TBD | TBD | Open |
| 5 | No data-row-level access control (all users see all units' data) | SAR #5, SSP AC-3 | Moderate (rises with real multi-unit data) | Define a data-level access model if used across units/commands with differing access needs | Engineering time; a policy decision on what compartmentalization is actually required | TBD | TBD | Open |
| 6 | No encryption at rest for warehouse/CSV/audit data | SAR #6, SSP SC-13 | Moderate (real data) | Add encryption at rest before storing real data | Engineering time | TBD | TBD | Open |
| 7 | No dependency vulnerability scanning | SAR #7, SSP RA-5 | Low | Integrate `pip-audit` or equivalent into the build/test process | Engineering time (small) | TBD | TBD | Open |
| 8 | No configuration hardening baseline (host, runtime, Streamlit server) | SAR #8, SSP CM-6 | Low (as-built); Moderate (network-exposed) | Apply a hardening checklist before network-facing deployment | Engineering time; a hardening standard to apply | TBD | TBD | Open |
| 9 | No independent security assessment or ATO | SAR #9, SSP CA-2/CA-6 | N/A (expected pre-assessment state) | See the ATO path section below | An assigned AO/SCA and an actual program | TBD | TBD | Open |
| 10 | No incident response plan | SSP "not yet applicable" note | Low (as-built); required before real deployment | Draft an IR plan once a real deployment is scoped | Engineering + ops time | TBD | TBD | Open |
| 11 | No backup/contingency plan | SSP "not yet applicable" note | Low (as-built, no production data to lose); required before real deployment | Draft a contingency plan once real data exists | Engineering + ops time | TBD | TBD | Open |

## Path to an actual Authority to Operate (ATO)

This section exists because "start working on an ATO" cannot literally mean producing one — **an ATO is a risk-acceptance decision made by a designated Authorizing Official (AO) for a real system in a real environment, not a document a development team (or an AI assistant) can generate or grant.** What follows is the realistic sequence of steps between where this prototype stands today and an actual ATO decision:

1. **A real program takes this on**, with an assigned System Owner, Information System Security Manager (ISSM)/Information System Security Officer (ISSO), and a designated Authorizing Official (or AO-designated representative). None of these roles exist for a solo prototype.
2. **The Information Owner confirms the categorization** in [SYSTEM_CATEGORIZATION.md](SYSTEM_CATEGORIZATION.md) — the Moderate target rating in this package is a reasonable planning assumption, not an authoritative determination.
3. **The high-severity POA&M items above are closed or formally risk-accepted** — most importantly items #1 (identity/PKI) and #2 (LLM interconnection), since both are prerequisites for touching real data at all, not hardening niceties.
4. **An independent Security Control Assessor (SCA) executes [SAP.md](SAP.md)** against a real deployment (not this synthetic-data build) and produces an actual SAR — distinct from the preliminary self-assessment in [SAR.md](SAR.md).
5. **The AO reviews the real SSP, SAR, and POA&M** and makes an actual risk-acceptance decision: full ATO, ATO with conditions, Interim ATO, or denial.

**What this repository provides toward that path:** a categorization starting point, a control-status baseline grounded in real code (not aspirational), a preliminary self-assessment naming real gaps honestly, and this POA&M. **What it cannot provide:** the organizational roles, the independent assessment, or the authorization decision itself — those require people and authority outside a development session, by design, because that separation is the entire point of RMF.
