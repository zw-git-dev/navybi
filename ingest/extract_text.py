"""
Structured extraction from free-text post-mission debrief narratives.

Same two-interpreter architecture as the conversational layer
(app/llm_interpret.py + app/nl_query.py): an LLM does the extraction when
one is configured, a deterministic rule-based extractor runs when it isn't
or when the call fails, and every record carries which one produced it. That
pattern is reused here deliberately rather than reinvented -- it's what lets
the system degrade to a working (if less capable) state instead of an outage
when a rate-limited free-tier model stops answering, and it keeps "how did
we get this value" answerable per-record, which is the same explainability
requirement the NL layer is held to.

A NOTE ON THE FALLBACK'S VOCABULARY, because it determines whether the
reported accuracy means anything: the rule-based extractor below is written
from domain vocabulary (what aircrew actually call these systems and
symptoms), NOT from the phrasings in data/generate_multimodal_data.py. If it
imported the generator's own symptom strings it would score ~100% by
construction and the accuracy number would be measuring nothing. The two
share concepts, not text -- so the extractor has to generalize the way it
would against narratives it hasn't seen.
"""
import hashlib
import json
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 45

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "extraction_cache.json")

EQUIPMENT_TYPES = ["Primary Aircraft/Vehicle", "Comms Suite", "Sensor Package"]
SEVERITIES = ["Minor", "Moderate", "Major"]
PHASES = ["Preflight", "Ingress", "On-Station", "Egress", "Recovery"]

# Independent domain vocabulary for the deterministic path -- how aircrew
# and maintainers actually refer to these systems, not the generator's
# sentence templates. Ordered most-specific-first within each list so a
# narrative mentioning both "datalink" and a generic "system" resolves to
# the specific one.
EQUIPMENT_VOCABULARY = {
    "Comms Suite": [
        "uhf", "vhf", "datalink", "data link", "secure voice", "radio",
        "comms", "communication", "freq", "frequency", "transmit", "xmit",
    ],
    "Sensor Package": [
        "radar", "flir", "targeting pod", "sensor", "eo/ir", "electro-optical",
        "gimbal", "sensor video", "track", "seeker",
    ],
    "Primary Aircraft/Vehicle": [
        "hydraulic", "landing gear", "gear position", "airframe", "flight control",
        "trim", "engine", "vibration", "fuel", "brake", "airfoil",
    ],
}

# Words indicating a discrepancy actually occurred. Presence alone isn't
# enough -- see the explicit negation check below, since "no discrepancies
# noted" contains "discrepanc".
DISCREPANCY_INDICATORS = [
    "experienced", "failure", "failed", "fault", "degraded", "intermittent",
    "malfunction", "anomaly", "unstable", "dropout", "loss of", "gripe",
    "write-up", "writeup", "wrote it up", "broke", "unserviceable", "down",
    "warning", "washing out", "garbl", "breaking up",
]

# Checked BEFORE the indicators: a clean sortie report frequently contains
# discrepancy words in negated form, and treating those as positives was the
# single biggest source of false positives when this was first written.
NEGATION_PATTERNS = [
    r"\bno\s+(discrepanc\w*|gripes?|issues?|write[- ]?ups?|faults?)\b",
    r"\bnothing\s+to\s+report\b",
    r"\bsystems?\s+nominal\b",
    r"\ball\s+systems?\s+performed\b",
    r"\bno\s+issues\b",
]

SEVERITY_VOCABULARY = {
    "Major": [
        "abort", "rtb", "return to base", "hard down", "significant impact",
        "immediately", "knocked us off", "entirely", "unable to continue",
    ],
    "Moderate": [
        "partial", "degraded our", "cost us", "worked around", "part of the event",
        "reduced", "impacted", "before next",
    ],
    "Minor": [
        "minor", "annoyance", "no impact", "did not affect", "nuisance",
        "logged it but",
    ],
}


def is_configured():
    return bool(OPENROUTER_API_KEY)


# ---------------------------------------------------------------- deterministic

def _detect_negation(text_lower):
    return any(re.search(p, text_lower) for p in NEGATION_PATTERNS)


def _split_sentences(text):
    """Crude but adequate sentence split -- debriefs are short declarative prose."""
    return [s.strip() for s in re.split(r"[.;!?]+", text) if s.strip()]


def extract_via_rules(narrative):
    """
    Deterministic extraction. Always returns a result (never fails), which
    is precisely why it's the fallback -- an LLM outage degrades capability
    here, it doesn't stop ingestion.

    Negation is evaluated PER SENTENCE, not per document, because debrief
    narratives routinely negate one phase while reporting a problem in
    another: "Standard preflight, no issues on the walkaround. During ingress
    we experienced an unstable FLIR gimbal." Document-level negation reads
    that as a clean sortie and silently drops a Major discrepancy -- the
    worst possible failure direction for a maintenance-relevant record, since
    it produces a confident "nothing wrong here" rather than an obvious gap.
    Found by testing this exact narrative shape, not by inspection.
    """
    sentences = _split_sentences(narrative.lower())

    # A sentence is positive evidence if it reports a problem and isn't
    # itself negated. Collecting the positive sentences (rather than a single
    # boolean over the whole document) also gives the field extraction below
    # a much cleaner region to work from.
    positive = [
        s for s in sentences
        if any(ind in s for ind in DISCREPANCY_INDICATORS) and not _detect_negation(s)
    ]

    if not positive:
        return {
            "has_discrepancy": False,
            "equipment_type": None,
            "severity": None,
            "phase": None,
            "extracted_by": "rules",
        }

    # Two regions, because the fields need different scopes. The tightest
    # region (sentences that actually report the problem) is right for
    # equipment and phase, where a wider window pulls in the wrong answer --
    # "Standard preflight, no issues" would otherwise set phase=Preflight for
    # a problem that happened during egress. But severity is usually asserted
    # in a FOLLOWING sentence that carries no discrepancy verb of its own
    # ("Mission aborted, this needs mx attention immediately"), so scoring it
    # against the tight region alone silently loses it. Widening severity to
    # all non-negated prose is safe: once a discrepancy is established, a
    # severity statement anywhere in the report is describing that
    # discrepancy.
    evidence = " ".join(positive)
    non_negated = " ".join(s for s in sentences if not _detect_negation(s))

    def _score_equipment(region):
        scores = {
            equip: sum(1 for term in terms if term in region)
            for equip, terms in EQUIPMENT_VOCABULARY.items()
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else None

    # Score by term count rather than first hit: a narrative can mention a
    # system in passing while the actual gripe is elsewhere, and weight of
    # evidence beats document order.
    equipment = _score_equipment(evidence) or _score_equipment(non_negated)

    severity = None
    for level in ("Major", "Moderate", "Minor"):  # most severe wins ties
        if any(term in non_negated for term in SEVERITY_VOCABULARY[level]):
            severity = level
            break

    phase = (next((p for p in PHASES if p.lower() in evidence), None)
             or next((p for p in PHASES if p.lower() in non_negated), None))

    return {
        "has_discrepancy": True,
        "equipment_type": equipment,
        "severity": severity,
        "phase": phase,
        "extracted_by": "rules",
    }


# ------------------------------------------------------------------------- LLM

_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "extract_debrief_facts",
        "description": (
            "Extract structured maintenance-relevant facts from a Navy post-mission "
            "debrief narrative. The narrative is informal prose and may use "
            "abbreviations, all-caps, or colloquial aircrew phrasing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "has_discrepancy": {
                    "type": "boolean",
                    "description": "True only if the narrative describes an actual equipment problem. A report explicitly stating no gripes/no discrepancies is false.",
                },
                "equipment_type": {
                    "type": ["string", "null"],
                    "enum": EQUIPMENT_TYPES + [None],
                    "description": "Which equipment category the problem affected. Map colloquial terms: radio/UHF/datalink/secure voice -> Comms Suite; radar/FLIR/targeting pod -> Sensor Package; hydraulics/gear/airframe/flight controls -> Primary Aircraft/Vehicle. Null if no discrepancy.",
                },
                "severity": {
                    "type": ["string", "null"],
                    "enum": SEVERITIES + [None],
                    "description": "Major if the mission was aborted or aircraft grounded; Moderate if mission effectiveness was reduced; Minor if logged with no mission impact. Null if no discrepancy.",
                },
                "phase": {
                    "type": ["string", "null"],
                    "enum": PHASES + [None],
                    "description": "Mission phase during which the problem occurred. Null if no discrepancy or not stated.",
                },
            },
            "required": ["has_discrepancy"],
        },
    },
}


def extract_via_llm(narrative):
    """
    Returns a result dict, or None if the call failed for any reason -- the
    caller falls back to rules on None. Deliberately does NOT raise: an
    ingestion run over hundreds of documents shouldn't abort because one
    API call timed out.
    """
    if not is_configured():
        return None

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content":
                        "You extract structured facts from Navy post-mission debrief narratives "
                        "by calling the extract_debrief_facts function. Only use the enumerated "
                        "values provided; never invent an equipment category."},
                    {"role": "user", "content": narrative},
                ],
                "tools": [_TOOL_SCHEMA],
                "tool_choice": {"type": "function", "function": {"name": "extract_debrief_facts"}},
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        tool_calls = resp.json()["choices"][0]["message"].get("tool_calls") or []
        if not tool_calls:
            return None
        args = json.loads(tool_calls[0]["function"]["arguments"])
    except Exception:
        return None

    # Validate against the known vocabulary rather than trusting the model's
    # strings -- same reasoning as app/llm_interpret.py's entity validation.
    # An out-of-enum value here would flow into the semantic layer as a
    # dimension nothing else shares, quietly fragmenting the conformed
    # equipment_type vocabulary the cross-source analytics depend on.
    equipment = args.get("equipment_type")
    if equipment not in EQUIPMENT_TYPES:
        equipment = None
    severity = args.get("severity")
    if severity not in SEVERITIES:
        severity = None
    phase = args.get("phase")
    if phase not in PHASES:
        phase = None

    has_discrepancy = bool(args.get("has_discrepancy"))
    if not has_discrepancy:
        equipment = severity = phase = None

    return {
        "has_discrepancy": has_discrepancy,
        "equipment_type": equipment,
        "severity": severity,
        "phase": phase,
        "extracted_by": "llm",
    }


# ------------------------------------------------------------------- interface

def _load_cache():
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
    except OSError:
        pass


def extract(narrative, use_cache=True):
    """
    Extract structured facts from one narrative, preferring the LLM and
    falling back to rules.

    Cached by content hash: re-running ingestion over an unchanged corpus
    shouldn't re-spend API calls, and on a rate-limited free tier it's the
    difference between a run that completes and one that degrades to rules
    halfway through for no reason.
    """
    key = hashlib.sha256(narrative.encode("utf-8")).hexdigest()[:16]
    cache = _load_cache() if use_cache else {}

    if use_cache and key in cache:
        result = dict(cache[key])
        result["from_cache"] = True
        return result

    result = extract_via_llm(narrative) or extract_via_rules(narrative)
    result["from_cache"] = False

    if use_cache:
        cache[key] = {k: v for k, v in result.items() if k != "from_cache"}
        _save_cache(cache)

    return result
