"""
Tests for the multimodal extraction layer.

Weighted toward the deterministic paths and the specific failure modes found
during development, rather than toward the LLM path -- an LLM call is
non-deterministic and rate-limited, so asserting on its output would produce
a flaky suite that fails for reasons unrelated to the code. The rules
extractor is what runs when the LLM is unavailable, which makes it the part
that most needs to keep working.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from ingest import extract_image, extract_text

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


# --------------------------------------------------------------- text: basics

def test_clean_sortie_reports_no_discrepancy():
    r = extract_text.extract_via_rules(
        "Brief and walk on time, normal start sequence. No gripes this sortie."
    )
    assert r["has_discrepancy"] is False
    assert r["equipment_type"] is None


def test_maps_colloquial_terms_to_equipment_vocabulary():
    """
    The narratives never name the catalog equipment type -- they say "secure
    voice" or "FLIR". Extraction that only worked on the literal category
    name would be string matching, not extraction.
    """
    r = extract_text.extract_via_rules(
        "During recovery we experienced degraded secure voice quality. "
        "Degraded our effectiveness for part of the event."
    )
    assert r["equipment_type"] == "Comms Suite"

    r = extract_text.extract_via_rules(
        "During ingress we experienced an unstable FLIR gimbal. Partial mission impact."
    )
    assert r["equipment_type"] == "Sensor Package"


@pytest.mark.parametrize("narrative,expected", [
    ("During egress we experienced a hydraulic leak. Mission aborted, RTB immediately.", "Major"),
    ("During ingress we experienced radar returns washing out. Cost us time on station.", "Moderate"),
    ("During on-station we experienced intermittent UHF dropouts. Logged it but it did not affect the tasking.", "Minor"),
])
def test_severity_inferred_from_mission_impact(narrative, expected):
    assert extract_text.extract_via_rules(narrative)["severity"] == expected


# ------------------------------------------------- text: regression, scoped negation

def test_negation_is_scoped_to_its_own_clause():
    """
    Regression. A debrief that reports a clean preflight and THEN a real
    discrepancy was being read as a clean sortie, because negation was
    evaluated over the whole document: "no issues on the walkaround" masked
    an unstable FLIR gimbal reported two sentences later.

    This is the worst failure direction available here -- it doesn't produce
    a visible gap, it produces a confident "nothing wrong," and a Major
    discrepancy silently never reaches the warehouse.
    """
    r = extract_text.extract_via_rules(
        "STANDARD PREFLIGHT, NO ISSUES ON THE WALKAROUND. "
        "DURING INGRESS WE EXPERIENCED AN UNSTABLE FLIR GIMBAL. "
        "PARTIAL MSN IMPACT, RECOMMEND MX LOOK AT IT BEFORE NEXT GO."
    )
    assert r["has_discrepancy"] is True
    assert r["equipment_type"] == "Sensor Package"
    assert r["phase"] == "Ingress"


def test_phase_comes_from_the_discrepancy_not_the_first_phase_mentioned():
    """
    Companion to the above: "Standard preflight..." must not set the phase
    for a problem that happened during egress.
    """
    r = extract_text.extract_via_rules(
        "Standard preflight, no issues on the walkaround. "
        "During egress we experienced a hydraulic indication. Mission aborted."
    )
    assert r["phase"] == "Egress"


def test_severity_recovered_from_a_following_sentence():
    """
    The severity assessment routinely sits in its own sentence with no
    discrepancy verb ("Mission aborted, this needs mx attention"). Scoring
    severity only against sentences that report the problem loses it.
    """
    r = extract_text.extract_via_rules(
        "Launched as fragged. During egress we experienced a hydraulic indication "
        "on the number two system. Mission aborted, this needs maintenance attention immediately."
    )
    assert r["severity"] == "Major"


def test_llm_output_is_validated_against_the_known_vocabulary():
    """
    An out-of-enum equipment value must be dropped, not passed through. If it
    reached the warehouse it would fragment the conformed equipment_type
    dimension that the cross-source corroboration measure depends on.
    """
    import json
    from unittest.mock import patch

    fake = {"choices": [{"message": {"tool_calls": [{"function": {"arguments": json.dumps({
        "has_discrepancy": True,
        "equipment_type": "Quantum Torpedo Bay",  # not in the vocabulary
        "severity": "Catastrophic",               # not in the vocabulary
        "phase": "Ingress",
    })}}]}}]}

    class Resp:
        def raise_for_status(self): pass
        def json(self): return fake

    with patch.object(extract_text, "OPENROUTER_API_KEY", "test-key"), \
         patch("ingest.extract_text.requests.post", return_value=Resp()):
        r = extract_text.extract_via_llm("something odd happened")

    assert r["has_discrepancy"] is True
    assert r["equipment_type"] is None
    assert r["severity"] is None
    assert r["phase"] == "Ingress"  # this one WAS valid and should survive


# -------------------------------------------------------------- image: parsing

def test_fuzzy_match_tolerates_ocr_damage_but_refuses_weak_evidence():
    assert extract_image._fuzzy_match("Comms Suile", extract_image.EQUIPMENT_TYPES) == "Comms Suite"
    assert extract_image._fuzzy_match("Minor", extract_image.SEVERITIES) == "Minor"
    # Nothing recognizable -> None, rather than the nearest guess. A wrong
    # value here is worse than a blank.
    assert extract_image._fuzzy_match("~~~", extract_image.EQUIPMENT_TYPES) is None
    assert extract_image._fuzzy_match("", extract_image.SEVERITIES) is None


def test_downtime_not_stolen_from_the_resolved_row():
    """
    Regression. When the DOWNTIME row held no value, the parser fell through
    to the next row -- RESOLVED -- and character-confusion repair turned
    "RESOLVED: NO" into "RE50LVED: N0", yielding a fabricated downtime of 50
    hours. A missing value has to stay missing.
    """
    rows = [
        [(120, "DOWNTIME"), (350, "HRS:")],
        [(120, "RESOLVED:"), (680, "NO")],
    ]
    fields = extract_image.extract_fields(rows)
    assert fields["downtime_hours"] is None
    assert fields["resolved"] is False


def test_orphan_closed_vocabulary_value_is_recovered():
    """
    OCR sometimes drops a label while reading its value cleanly. Because
    severities are a closed, disjoint vocabulary, a bare "Minor" on its own
    row is unambiguously the severity and shouldn't be discarded.
    """
    rows = [
        [(120, "EQUIPMENT:"), (680, "Comms"), (800, "Suite")],
        [(680, "Minor")],  # SEVERITY label was dropped by OCR
    ]
    fields = extract_image.extract_fields(rows)
    assert fields["severity"] == "Minor"
    assert fields["equipment_type"] == "Comms Suite"


def test_unit_id_survives_character_confusion():
    """U05 is routinely read as 'v0S' or 'u05' at this resolution."""
    for raw in ["v0S", "u05", "U05", "vos"]:
        rows = [[(120, "UNIT"), (250, "ID:"), (680, raw)]]
        assert extract_image.extract_fields(rows)["unit_id"] == "U05"


# ------------------------------------------------------ corpus-level integration

@pytest.mark.skipif(
    not os.path.isdir(os.path.join(RAW_DIR, "forms")),
    reason="multimodal corpus not generated (run data/generate_multimodal_data.py)",
)
@pytest.mark.skipif(not extract_image.is_available(), reason="tesseract not installed")
def test_ocr_accuracy_holds_on_the_labeled_corpus():
    """
    Guards the measured accuracy against regression. The threshold is set
    below the observed 87% so ordinary OCR variation doesn't fail the build,
    while a real degradation still would.

    Also asserts the failure MODE, which matters as much as the rate: errors
    should overwhelmingly be missing values (a visible gap) rather than wrong
    values (a silent falsehood propagating into a measure).
    """
    import json

    with open(os.path.join(RAW_DIR, "form_manifest.json")) as f:
        truth = {t["form_id"]: t for t in json.load(f)}

    fields = ["unit_id", "equipment_type", "severity", "downtime_hours", "resolved"]
    correct = wrong = missing = 0
    for form_id, t in truth.items():
        extracted, _ = extract_image.extract(os.path.join(RAW_DIR, "forms", f"{form_id}.png"))
        for key in fields:
            got, want = extracted[key], t[f"truth_{key}"]
            if got == want:
                correct += 1
            elif got is None:
                missing += 1
            else:
                wrong += 1

    total = len(truth) * len(fields)
    assert correct / total >= 0.80, f"OCR field accuracy regressed: {correct}/{total}"
    assert wrong <= missing, (
        f"failure mode inverted: {wrong} wrong vs {missing} missing -- the extractor "
        "should fail toward blanks, not toward confident wrong values"
    )
