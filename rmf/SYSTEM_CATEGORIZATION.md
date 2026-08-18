# System Categorization (FIPS 199 / NIST SP 800-60)

**System name:** NavyBI Prototype
**Categorization performed by:** Development team (self-assessment) — see the "Who can actually do this" note at the end. Not a substitute for Information Owner / Authorizing Official (AO) confirmation.
**Date:** See git history for this file's commit date.

## Why this document has two categorizations, not one

This prototype currently runs on 100% fabricated, synthetic data (`data/generate_synthetic_data.py`) — there is no real unit, personnel, mission, training, or maintenance information anywhere in it. Categorizing it as if it already held real post-mission reporting data would overstate the actual current risk. Categorizing it only for its current synthetic-data state, and stopping there, would understate what any real deployment would need to plan for. So both are documented explicitly, and the gap between them is the point.

## As-built categorization (current state: synthetic data only)

| Security objective | Impact | Rationale |
|---|---|---|
| Confidentiality | **Low** | All data is fabricated. Unauthorized disclosure of this system's contents discloses nothing about any real unit, person, mission, or operation. |
| Integrity | **Low** | Corrupted or tampered data in this system has no operational consequence — it's a demo dataset, not a system anyone would act on. |
| Availability | **Low** | No operational process depends on this system being up. Downtime is an inconvenience to whoever is evaluating the prototype, nothing more. |

**As-built overall categorization: LOW** (high-water mark of the three objectives).

## Target categorization (real deployment, real post-mission reporting data)

This is the categorization that would actually apply if this system (or something built from it) were pointed at real Navy post-mission reporting data.

| Security objective | Impact | Rationale |
|---|---|---|
| Confidentiality | **Moderate** | Post-mission reports plausibly contain Controlled Unclassified Information (CUI) — unit readiness, training status, mission activity patterns. Unauthorized disclosure could cause a serious adverse effect on operations, assets, or individuals (e.g., revealing readiness gaps or personnel information), but this is reporting/analytics data, not classified operational plans — not assessed as High. |
| Integrity | **Moderate** | Leadership and unit-level decisions about training, readiness, and maintenance priorities could be influenced by this system's outputs. Tampered or silently-wrong data (see QUESTION_TEST_LOG.md for how seriously this project already treats "confidently wrong" as a failure mode) could cause a serious, but not catastrophic, adverse effect. |
| Availability | **Moderate** | Used to inform routine, non-real-time decisions. A service disruption is a serious operational inconvenience — delayed reporting, delayed decisions — not a mission-critical failure the way a real-time C2 system's outage would be. |

**Target overall categorization: MODERATE** (high-water mark of the three objectives).

## What this implies

A Moderate categorization pulls in the NIST SP 800-53 Rev 5 Moderate control baseline (a materially larger set of controls than Low) for any real deployment. See [SSP.md](SSP.md) for control-by-control implementation status against a representative subset of that baseline, and [POAM.md](POAM.md) for what's not yet in place.

## Who can actually do this

**This categorization was performed by the development team as a starting point, not a substitute for the real process.** Under RMF, system categorization is properly a joint determination by the Information Owner and the Authorizing Official (or their designated representative), informed by the actual data sensitivity and mission impact — not by whoever built the prototype. Treat the "Moderate" target rating above as a reasonable planning assumption to build toward, not a rating this document has the authority to finalize.
