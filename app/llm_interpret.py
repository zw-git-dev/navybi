"""
Real LLM-based question interpretation via OpenRouter -- the "swap point"
this project's architecture was built for from the start (see
app/nl_query.py's module docstring). This module is intentionally the ONLY
place that knows an LLM exists: it takes a question, a lookup of known
entity vocabulary, and the INTENTS registry, and returns the exact same
(matched_intent, dimension, entity_filter) shape the keyword matcher
produces. Everything downstream in interpret_question() -- dimension
resolution via entity_to_dimension, sort-order detection, the
scope-mismatch caveat mechanism, month-window parsing -- is completely
unaware of whether its input came from here or from keyword matching.

Configuration is via environment variables (loaded from a local .env file,
gitignored, never committed):
    OPENROUTER_API_KEY   required to enable this path at all
    OPENROUTER_MODEL     defaults to nvidia/nemotron-3-ultra-550b-a55b:free

If OPENROUTER_API_KEY isn't set, is_configured() returns False and
app/nl_query.py falls back to the keyword matcher entirely -- this file's
absence-of-a-key behavior is the same "no LLM available" state the rest of
the codebase already documents extensively (see QUESTION_TEST_LOG.md).
"""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 45  # this model reasons by default; free-tier + reasoning is slow

ENTITY_TYPE_TO_LOOKUP_KEY = {
    "unit_name": "unit_names",
    "mission_type": "mission_types",
    "equipment_type": "equipment_types",
    "certification": "certifications",
}


def is_configured():
    return bool(OPENROUTER_API_KEY)


def _build_tool_schema(intents):
    intent_ids = [i["id"] for i in intents] + ["none"]
    dims_desc = "; ".join(
        f"{i['id']} -- {i.get('llm_description', '')} (dimensions: {', '.join(i['views'].keys())})"
        for i in intents
    )
    return {
        "type": "function",
        "function": {
            "name": "interpret_bi_question",
            "description": (
                "Classify a natural-language question about Navy post-mission reporting data "
                "into exactly one of a fixed set of supported measures, or 'none' if the "
                "question doesn't clearly match any of them. Never invent a measure, "
                "dimension, or entity value that wasn't explicitly provided to you -- if "
                "you're not sure, use 'none' rather than guessing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "intent_id": {
                        "type": "string",
                        "enum": intent_ids,
                        "description": f"Which measure the question is about. Available measures and their valid dimensions: {dims_desc}. Use 'none' if nothing matches.",
                    },
                    "dimension": {
                        "type": "string",
                        "description": "Which dimension to group/filter by for the chosen intent -- must be one of that intent's valid dimensions listed above. Omit if intent_id is 'none'.",
                    },
                    "entity_type": {
                        "type": "string",
                        "enum": list(ENTITY_TYPE_TO_LOOKUP_KEY.keys()) + ["none"],
                        "description": "If the question names a specific unit, mission type, equipment type, or certification, which kind of entity that is. Otherwise 'none'.",
                    },
                    "entity_value": {
                        "type": "string",
                        "description": "The named entity's EXACT string, copied verbatim from the provided list of valid values below -- never invented, abbreviated, or paraphrased. Omit if entity_type is 'none'.",
                    },
                },
                "required": ["intent_id"],
            },
        },
    }


def _build_system_prompt(lookup):
    return "\n".join([
        "You interpret questions about Navy post-mission reporting data by calling the interpret_bi_question function.",
        "Only use entity values from these exact lists -- never invent a name that isn't here:",
        "Units: " + ", ".join(sorted(set(lookup["unit_names"].values()))),
        "Mission types: " + ", ".join(sorted(set(lookup["mission_types"].values()))),
        "Equipment types: " + ", ".join(sorted(set(lookup["equipment_types"].values()))),
        "Certifications: " + ", ".join(sorted(set(lookup["certifications"].values()))),
    ])


def interpret_via_llm(question, lookup, intents):
    """
    Returns (status, matched_intent, dimension, entity_filter):
      "ok"       -- model confidently classified the question; use the result
      "no_match" -- model explicitly determined no measure applies; this is
                    an authoritative answer, NOT a failure -- the caller
                    should NOT fall back to the keyword matcher for this case,
                    since the model actually reasoned about it and said no
      "error"    -- the call failed, timed out, or returned something
                    unusable; the caller SHOULD fall back to the keyword
                    matcher for this case
    """
    if not is_configured():
        return ("error", None, None, None)

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": _build_system_prompt(lookup)},
                    {"role": "user", "content": question},
                ],
                "tools": [_build_tool_schema(intents)],
                "tool_choice": {"type": "function", "function": {"name": "interpret_bi_question"}},
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        message = resp.json()["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return ("error", None, None, None)
        args = json.loads(tool_calls[0]["function"]["arguments"])
    except Exception:
        return ("error", None, None, None)

    intent_id = args.get("intent_id")
    if not intent_id or intent_id == "none":
        return ("no_match", None, None, None)

    matched_intent = next((i for i in intents if i["id"] == intent_id), None)
    if matched_intent is None:
        # The model returned something outside the enum we gave it --
        # treat as a technical failure (fall back), not an authoritative "no".
        return ("error", None, None, None)

    dimension = args.get("dimension")
    if dimension not in matched_intent["views"]:
        dimension = matched_intent["default_dimension"]

    entity_filter = None
    lookup_key = ENTITY_TYPE_TO_LOOKUP_KEY.get(args.get("entity_type"))
    entity_value = args.get("entity_value")
    if lookup_key and entity_value:
        # Validate against the known vocabulary rather than trusting the
        # model's string verbatim -- an unvalidated hallucinated entity name
        # would otherwise silently produce a SQL filter matching zero rows,
        # which looks like "no data" rather than "the model made this up."
        valid_values = set(lookup[lookup_key].values())
        if entity_value in valid_values:
            entity_filter = (args["entity_type"], entity_value)

    return ("ok", matched_intent, dimension, entity_filter)
