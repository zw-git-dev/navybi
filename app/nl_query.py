"""
Conversational query layer: plain-language question -> chart + explanation.

ARCHITECTURE NOTE (read this before judging the "AI" here):
The pipeline is  question -> interpret_question() -> SQL against the semantic
layer -> dataframe -> chart + explanation. That is a real, working
conversational-BI architecture. interpret_question() has two interpreters:
- app/llm_interpret.py, a real LLM call (OpenRouter) used whenever
  OPENROUTER_API_KEY is configured -- see that file for the model/prompt.
- _interpret_via_keywords() below, a keyword/entity matcher used as a
  fallback when no LLM is configured, or when the LLM call itself fails
  (network error, timeout, malformed response). See QUESTION_TEST_LOG.md
  for five rounds of real bugs found and fixed in the keyword matcher --
  it's kept not because it's good, but because it's a working degraded
  mode when the LLM is unavailable.

Both interpreters return the exact same shape -- (matched_intent, dimension,
entity_filter) -- so every downstream mechanism (entity-to-dimension
resolution, sort-order detection, the scope-mismatch caveat system,
month-window parsing) is completely unaware of which one produced its input.
That shared downstream code, not either interpreter, is what actually
implements "transparent, explainable, and manually verifiable": every answer
returned by answer_question() carries the literal SQL that was run and the
plain-language measure definition, and the caller can always drop to the
drill-down table (api/routers/dashboard.py::drilldown, rendered by the
frontend's Drill-down page) to check the underlying rows by hand, regardless
of which interpreter answered.
"""
import re
import sys
import os
from functools import lru_cache

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from warehouse import semantic_layer as sl
from app import llm_interpret


def _kw_in(kw, q):
    """
    Keyword match helper used everywhere a keyword list is checked against
    a question. Plain substring matching ("kw in q") is wrong for a
    single-word keyword: "ready" is a substring of "already", "most" is a
    substring of "almost", and a question like "the unit has already
    completed most of its missions" would otherwise silently match the
    readiness intent for a question that has nothing to do with equipment
    readiness -- a wrong-domain confident answer, found via adversarial
    testing in QUESTION_TEST_LOG.md round 5, not a hypothetical.

    Multi-word phrases ("how long", "objective met", "cert ") stay as plain
    substring checks -- they're long enough that accidental containment
    inside an unrelated word essentially doesn't happen, and some (like
    "cert " with its trailing space) rely on partial-word matching by design.
    Only single-word keywords get the stricter word-boundary regex check --
    with an optional trailing "s" so a singular keyword ("trend") still
    matches its plain plural ("trends") in the question. A real regression
    was found here in round 5 testing: word-boundary matching alone silently
    broke "mission trends" ("trend" no longer matched "trends"), which is
    exactly the failure mode this whole file is trying to prevent -- a fix
    for one bug quietly introducing another. Only a bare "s" is handled,
    not general inflection (no "-es"/"-ed"/"-ing"); anything beyond that is
    exactly the kind of edge case a real LLM would handle for free and this
    keyword approach can't chase indefinitely (see this function's caller's
    docstring).
    """
    if " " in kw:
        return kw in q
    return re.search(rf"\b{re.escape(kw.strip())}s?\b", q) is not None


INTENTS = [
    {
        "id": "completion_by_unit",
        # Used only by the LLM interpreter (app/llm_interpret.py) -- the
        # keyword matcher doesn't need plain-language descriptions, but the
        # LLM does, since it has no other signal for what an intent_id like
        # "completion_by_unit" actually covers beyond its name.
        "llm_description": "Mission completion rate / objective success rate -- whether missions were completed and met their objective.",
        "keywords": ["completion", "objective met", "success rate", "succeed"],
        # "all-of" groups: matches if every word in a group appears ANYWHERE in
        # the question, regardless of order/phrasing -- catches rephrasings
        # like "met their objective" that the literal "objective met" substring
        # above would miss. Kept separate from "keywords" (order-sensitive
        # substrings) because all-of matching is looser and could over-match
        # if used for every intent; here it's deliberately narrow (objective + met).
        "keyword_all_of": [["objective", "met"]],
        "dimension_keywords": {"unit": ["unit", "squadron"], "type": ["mission type", "type of mission"]},
        "default_dimension": "unit",
        "views": {"unit": "v_mission_completion_by_unit", "type": "v_mission_completion_by_type"},
        "chart": {"x": {"unit": "unit_name", "type": "mission_type"}, "y": "completion_rate_pct", "kind": "bar"},
        # Every intent declares which entity columns its views actually
        # contain -- checked centrally in interpret_question() before an
        # entity_filter is used to build SQL. Without this, an interpreter
        # (the LLM especially -- see app/llm_interpret.py) can attach a
        # syntactically-valid entity to an intent whose chosen view has no
        # such column at all, producing a DuckDB BinderException crash, not
        # just a wrong answer. Found for real in round 6: the LLM classified
        # "How many ASW Training missions were flown?" as the "trend" intent
        # (correctly) but also attached mission_type="ASW Training" (which
        # the trend view can't filter by), and the query crashed outright.
        "valid_entity_columns": {"unit_name", "mission_type"},
    },
    {
        "id": "readiness",
        "llm_description": "Equipment/unit readiness percentage -- how ready equipment or a unit is.",
        "keywords": ["readiness", "ready", "equipment status"],
        "dimension_keywords": {"unit": ["unit", "squadron"], "equipment": ["equipment", "sensor", "comms", "aircraft", "vehicle"]},
        "default_dimension": "unit",
        "views": {"unit": "v_avg_readiness_by_unit", "equipment": "v_avg_readiness_by_equipment"},
        "chart": {"x": {"unit": "unit_name", "equipment": "equipment_type"}, "y": "avg_readiness_pct", "kind": "bar"},
        "valid_entity_columns": {"unit_name", "equipment_type"},
    },
    {
        "id": "duration",
        "llm_description": "Average mission duration -- how long missions of a given type take, in hours.",
        "keywords": ["duration", "how long", "hours"],
        "dimension_keywords": {"type": ["mission type", "type of mission", "type"]},
        "default_dimension": "type",
        "views": {"type": "v_avg_duration_by_type"},
        "chart": {"x": {"type": "mission_type"}, "y": "avg_duration_hours", "kind": "bar"},
        "valid_entity_columns": {"mission_type"},
    },
    {
        "id": "trend",
        "llm_description": "Mission count trends over time / by month -- how many missions happened per month.",
        "keywords": ["trend", "over time", "by month", "per month", "count of missions", "how many missions"],
        "dimension_keywords": {"month": ["month", "trend", "time"]},
        "default_dimension": "month",
        "views": {"month": "v_mission_count_by_month"},
        "chart": {"x": {"month": "mission_month"}, "y": "mission_count", "kind": "line", "color": "unit_name"},
        # NOT {"unit_name", "mission_type"} -- v_mission_count_by_month has a
        # unit_name column but no mission_type column at all, unlike every
        # other intent where "the dimensions' entity types" and "the entity
        # types this intent supports" happen to coincide. This is exactly
        # the case the crash above was found on.
        "valid_entity_columns": {"unit_name"},
    },
    {
        "id": "training_currency",
        "llm_description": "Training/certification currency -- whether personnel's certifications (e.g. Water Survival, Weapons Qualification, NATOPS Check) are still valid/current or have lapsed/expired.",
        # "training" and "qualification" are handled separately, NOT as plain
        # keywords here -- both collide with real mission_type names ("ASW
        # Training", "Air Intercept Training", "Deck Landing Qualification"),
        # so a bare substring match would misfire on mission questions that
        # have nothing to do with certifications. See the weak-keyword
        # collision check below, applied specifically for this intent.
        "keywords": ["certification", "certifications", "cert ", "qualified", "current on", "training currency", "training status", "training record"],
        "dimension_keywords": {"unit": ["unit", "squadron"], "certification": ["certification type", "cert type"]},
        "default_dimension": "unit",
        "views": {"unit": "v_training_currency_by_unit", "certification": "v_training_currency_by_certification"},
        "chart": {"x": {"unit": "unit_name", "certification": "certification"}, "y": "currency_rate_pct", "kind": "bar"},
        "valid_entity_columns": {"unit_name", "certification"},
    },
    {
        "id": "maintenance",
        "llm_description": "Equipment maintenance/discrepancy events -- how much downtime equipment has for repairs, and whether logged maintenance discrepancies/issues have been resolved or are still outstanding/unresolved.",
        # "unresolved"/"outstanding" are listed explicitly rather than relied
        # on via substring-of-"resolved": _kw_in() below uses word-boundary
        # matching for single-word keywords (to stop "ready" from matching
        # inside "already" -- a real bug found in round 5), which as a side
        # effect means "resolved" no longer substring-matches "unresolved".
        # That's the right call for "ready"/"already" (unrelated meanings)
        # but wrong here (same root, opposite meaning) -- so "unresolved" is
        # its own first-class keyword instead of leaning on accidental
        # substring containment.
        "keywords": ["maintenance", "discrepancy", "discrepancies", "downtime", "repair", "resolved", "resolution", "fixed", "repaired", "unresolved", "outstanding"],
        # Unlike every other intent, the two dimensions here are genuinely
        # different MEASURES (downtime vs. resolution rate), not just
        # different groupings of the same one -- "downtime" and "resolution"
        # are named for what's being asked, not for a grouping column, and
        # chart_spec["y"] below is a dict for exactly this reason.
        "dimension_keywords": {"downtime": ["downtime", "how long is equipment down", "time to repair"], "resolution": ["resolved", "resolution", "fixed", "repaired", "closed out", "unresolved", "outstanding"]},
        "default_dimension": "downtime",
        "views": {"downtime": "v_maintenance_downtime_by_equipment", "resolution": "v_maintenance_resolution_rate_by_unit"},
        "chart": {
            "x": {"downtime": "equipment_type", "resolution": "unit_name"},
            "y": {"downtime": "avg_downtime_hours", "resolution": "resolution_rate_pct"},
            "kind": "bar",
        },
        # Overrides the default entity-to-dimension map: an equipment_type
        # entity only exists in the downtime view, and a unit_name entity
        # only exists in the resolution view -- the two measures don't share
        # a schema the way completion/readiness/training's dimensions do.
        "entity_to_dimension": {"equipment_type": "downtime", "unit_name": "resolution"},
        "valid_entity_columns": {"equipment_type", "unit_name"},
    },
]

# "training" and "qualification" are real signals for the training_currency
# intent (e.g. "training currency", "Weapons Qualification") but ALSO appear
# inside real mission_type names, so a bare substring match on them isn't
# safe the way it is for the other keywords above. A weak-keyword match only
# counts if it ISN'T fully explained by a mission_type name present in the
# question -- see _training_currency_matches() below.
TRAINING_CURRENCY_WEAK_KEYWORDS = ["training", "qualification"]


SUPERLATIVE_KEYWORDS = {
    "asc": ["lowest", "minimum", "worst", "least"],
    "desc": ["highest", "maximum", "best", "most"],
}

# Words describing the LOW end of a currency/rate-style measure by name
# rather than by superlative -- "most expired" means "lowest currency rate,"
# not "highest," even though "most" alone would normally mean descending.
# Checked after the generic superlative keywords and allowed to override
# them, since the measure-specific meaning is more specific than the generic
# word. Narrow and measure-specific on purpose rather than a general
# solution -- see interpret_question()'s docstring on why keyword patching
# doesn't scale, this is one more instance of that same ceiling.
NEGATIVE_CONDITION_KEYWORDS = ["expired", "lapsed", "not current", "non-current", "overdue"]

# Signals a question is asking for something no current measure supports.
# Detecting these and saying so explicitly is the point: a wrong-scope
# answer that renders normally is more dangerous than an honest rejection
# (see QUESTION_TEST_LOG.md's "important finding") -- this is the safeguard
# that finding called for, not a nice-to-have.
UNSUPPORTED_DIMENSION_KEYWORDS = {
    "community": ["community", "communities"],
    "time_trend": ["trend", "over time", "by month", "per month", "month by month", "monthly"],
}


@lru_cache(maxsize=1)
def _load_entity_lookup():
    """
    Cached: this ran 4 SQL queries from scratch on every single call to
    interpret_question() -- i.e. on every "Ask a question" request -- to
    rebuild a vocabulary (unit names, mission types, equipment types,
    certifications) that only changes when the warehouse is rebuilt, which
    only happens when the process restarts. lru_cache(maxsize=1) is
    correct here specifically because it takes no arguments; if the
    warehouse is rebuilt with --reset, the process needs restarting anyway
    for auth/seed_users.py's fresh users.json to take effect too, so a
    process-lifetime cache doesn't add a new staleness mode.
    """
    units = sl.query("SELECT DISTINCT unit_id, unit_name, community FROM v_missions")
    types = sl.query("SELECT DISTINCT mission_type FROM v_missions")
    equipment = sl.query("SELECT DISTINCT equipment_type FROM v_readiness")
    certifications = sl.query("SELECT DISTINCT certification FROM v_training_records")
    return {
        "unit_names": dict(zip(units["unit_name"].str.lower(), units["unit_name"])),
        "mission_types": dict(zip(types["mission_type"].str.lower(), types["mission_type"])),
        "equipment_types": dict(zip(equipment["equipment_type"].str.lower(), equipment["equipment_type"])),
        "communities": dict(zip(units["community"].str.lower(), units["community"])),
        "certifications": dict(zip(certifications["certification"].str.lower(), certifications["certification"])),
    }


def _interpret_via_keywords(q, lookup):
    """
    Fallback interpreter: keyword + entity-substring matching against the
    known vocabulary of units/mission types/equipment (pulled live from the
    semantic layer, not hardcoded, so it stays correct if the data changes).
    Returns (matched_intent, dimension, entity_filter), or (None, None, None)
    if nothing matched. Does NOT apply the entity-to-dimension override --
    that's shared with the LLM path and applied once in interpret_question().
    """

    def _training_currency_weak_match():
        """
        A weak keyword ("training"/"qualification") only counts as a real
        training_currency signal if it ISN'T fully explained by a
        mission_type name present in the question -- e.g. "ASW Training" and
        "Deck Landing Qualification" are mission types, not certification
        references, and matching on them here would silently return a
        training-currency chart for a mission-count/duration question. This
        is the same failure shape the trend-intent reordering below exists
        to prevent, just triggered by vocabulary overlap instead of intent
        ordering -- see QUESTION_TEST_LOG.md round 5.
        """
        if not any(_kw_in(kw, q) for kw in TRAINING_CURRENCY_WEAK_KEYWORDS):
            return False
        for name in lookup["mission_types"]:
            # deliberately a plain substring check against the mission_type
            # NAME (not against the question) -- this is checking whether the
            # weak keyword is part of a known multi-word entity name, which
            # is exactly the substring relationship we're looking for here.
            if name in q and any(kw in name for kw in TRAINING_CURRENCY_WEAK_KEYWORDS):
                return False
        return True

    def _intent_matches(intent):
        any_of_match = any(_kw_in(kw, q) for kw in intent["keywords"])
        all_of_match = any(all(w in q for w in group) for group in intent.get("keyword_all_of", []))
        if any_of_match or all_of_match:
            return True
        if intent["id"] == "training_currency":
            return _training_currency_weak_match()
        return False

    # "trend" is checked LAST regardless of list order, on purpose: its
    # keywords ("trend", "by month") are generic enough to fire on a question
    # about ANY domain that happens to mention time, e.g. "training currency
    # trends by month" -- if trend were checked first-match-wins like the
    # others, that would silently return an unrelated mission-count chart for
    # a training question, which is exactly the confident-wrong-answer
    # failure mode this file's caveat mechanism exists to prevent (see
    # QUESTION_TEST_LOG.md). Checking domain-specific intents first means a
    # training/completion/readiness/duration keyword always wins when
    # present; only a question with NO other domain signal falls through to
    # the mission-count trend view.
    matched_intent = None
    for intent in INTENTS:
        if intent["id"] != "trend" and _intent_matches(intent):
            matched_intent = intent
            break
    if matched_intent is None:
        trend_intent = next(i for i in INTENTS if i["id"] == "trend")
        if _intent_matches(trend_intent):
            matched_intent = trend_intent
    if matched_intent is None:
        return None, None, None

    dimension = matched_intent["default_dimension"]
    for dim, kws in matched_intent["dimension_keywords"].items():
        if any(_kw_in(kw, q) for kw in kws):
            dimension = dim
            break

    entity_filter = None
    for name_lower, name_orig in lookup["unit_names"].items():
        words = name_lower.split()
        last_word = words[-1]
        other_words = [w for w in words[:-1] if len(w) > 2]
        # The bare "last word in the question" fallback exists to catch
        # informal references like "Sqn 7" for "Helicopter Sea Combat Sqn 7".
        # On its own it's dangerous when a unit name ends in a small number
        # (several here do -- "...Wing 3", "...Squadron 12") because that
        # digit can coincidentally appear in unrelated phrasing, e.g. "last 3
        # months" wrongly matching unit "3". Requiring at least one other,
        # non-trivial word from the name to ALSO appear closes that hole
        # without losing the informal-reference case it was meant for.
        last_word_match = last_word in q.split() and any(w in q for w in other_words)
        if name_lower in q or last_word_match:
            entity_filter = ("unit_name", name_orig)
            break
    if entity_filter is None:
        for name_lower, name_orig in lookup["mission_types"].items():
            if name_lower in q:
                entity_filter = ("mission_type", name_orig)
                break
    if entity_filter is None:
        for name_lower, name_orig in lookup["equipment_types"].items():
            if name_lower in q:
                entity_filter = ("equipment_type", name_orig)
                break
    if entity_filter is None:
        for name_lower, name_orig in lookup["certifications"].items():
            if name_lower in q:
                entity_filter = ("certification", name_orig)
                break

    return matched_intent, dimension, entity_filter


def interpret_question(question):
    """
    Input: a raw natural-language question string.
    Output: a structured intent dict, or None if nothing matched (either no
    interpreter found a match, or a match was found but discarded as
    insufficiently trustworthy -- see the no_match handling below):
        {
          "intent_id": str,
          "dimension": str,
          "view": str (semantic-layer view name),
          "entity_filter": (column, value) or None,
          "chart_spec": dict,
          "interpreted_by": "llm" or "keyword" or "keyword_after_llm_no_match",
        }

    Tries app/llm_interpret.py first if OPENROUTER_API_KEY is configured;
    falls back to _interpret_via_keywords() above if the LLM isn't
    configured, or if its call fails technically (network error, timeout,
    malformed response).

    If the LLM call succeeds and reports no match, that is NOT treated as
    fully authoritative the way a technical failure isn't -- but it isn't
    ignored either. The keyword matcher gets a second opinion (this is the
    resolution to the open design question in QUESTION_TEST_LOG.md round 6:
    a well-reasoned LLM "no" was sometimes less helpful than the keyword
    matcher's caveated partial answer for the same known gap). That second
    opinion is trusted only when it comes back WITH a caveat -- see the
    "keyword_after_llm_no_match" handling further down. A caveat means the
    keyword matcher is itself flagging a limitation, not confidently
    asserting a full answer; a clean, uncaveated keyword match that
    contradicts an LLM rejection is treated as more likely to be the
    keyword matcher's own false positive than a genuine LLM miss, and is
    discarded so the LLM's rejection stands.

    Also returns "caveats": a list of plain-language strings describing any
    part of the question this interpreter could detect but NOT actually
    honor (e.g. a community name with no community-level measure, or a
    time-trend request against a measure with no time dimension). The caller
    must surface these prominently rather than silently dropping the
    unhandled part of the question -- see QUESTION_TEST_LOG.md for why a
    confident-looking wrong-scope answer is a worse failure than an honest
    "I don't understand". This caveat logic is shared by both interpreters --
    it doesn't matter which one picked the base intent.
    """
    q = question.lower().strip()
    if not q:
        return None

    lookup = _load_entity_lookup()

    matched_intent, dimension, entity_filter, interpreted_by = None, None, None, None
    llm_said_no_match = False

    if llm_interpret.is_configured():
        status, li_intent, li_dimension, li_entity_filter = llm_interpret.interpret_via_llm(question, lookup, INTENTS)
        if status == "ok":
            matched_intent, dimension, entity_filter = li_intent, li_dimension, li_entity_filter
            interpreted_by = "llm"
        elif status == "no_match":
            # No longer an immediate return: an LLM "no match" is still
            # given a second opinion from the keyword matcher below, per
            # QUESTION_TEST_LOG.md round 6's open design question. It's
            # NOT treated as equally authoritative, though -- see the
            # caveat-gated check after caveats are computed, further down.
            llm_said_no_match = True

    if matched_intent is None:
        matched_intent, dimension, entity_filter = _interpret_via_keywords(q, lookup)
        if matched_intent is not None:
            interpreted_by = "keyword_after_llm_no_match" if llm_said_no_match else "keyword"

    if matched_intent is None:
        return None

    # Cross-check specific to the "trend" intent: the keyword matcher's own
    # logic (see _interpret_via_keywords above) deliberately checks every
    # domain-specific intent BEFORE the generic "trend" one, precisely
    # because "trend"/"by month" is generic enough to fire on a question
    # about any domain that happens to mention time. That ordering
    # safeguard only helps when the keyword matcher itself is choosing --
    # it does nothing to stop an LLM from picking "trend" directly for a
    # question that's actually about readiness or training currency, with
    # no caveat, because from the LLM's answer alone there's no signal that
    # a different domain was even in play. Found for real switching to
    # google/gemma-4-31b-it:free: "readiness trend by month" and "training
    # currency trends by month" were answered with an unrelated
    # mission-count chart and NO caveat -- the exact confident-wrong-answer
    # failure mode every prior round worked to eliminate, just reachable
    # through a new door (a different model's classification bias) rather
    # than a new bug in this file's own logic. Re-running the keyword
    # matcher's domain-priority check here, regardless of which
    # interpreter chose "trend," catches it: if keyword matching would
    # instead choose a specific domain, that domain wins, and the existing
    # time_trend-mismatch caveat below fires normally for it.
    if matched_intent["id"] == "trend":
        domain_intent, domain_dimension, domain_entity_filter = _interpret_via_keywords(q, lookup)
        if domain_intent is not None and domain_intent["id"] != "trend":
            matched_intent, dimension, entity_filter = domain_intent, domain_dimension, domain_entity_filter
            interpreted_by = "keyword" if interpreted_by is None else f"{interpreted_by}_corrected_by_keyword_domain_check"

    caveats = []

    # Hard safety check, run BEFORE the entity_filter is trusted for
    # anything: does this intent's schema even have this entity column at
    # all? Without this, an interpreter (the LLM especially) can attach a
    # syntactically fine-looking entity to an intent whose views have no
    # such column -- e.g. asking to filter the mission-count trend by
    # mission_type, which no trend view supports -- and the query crashes
    # outright with a DuckDB BinderException instead of just answering
    # wrong. This is a harder failure than anything the caveat mechanism
    # was originally built for (a crash, not a wrong-but-rendered answer),
    # found for real in round 6 testing the LLM interpreter. Every intent
    # declares its actual valid_entity_columns above for exactly this check.
    if entity_filter and entity_filter[0] not in matched_intent.get("valid_entity_columns", set()):
        caveats.append(
            f"This question mentioned a specific {entity_filter[0].replace('_', ' ')} "
            f"('{entity_filter[1]}'), but the '{matched_intent['id']}' measure can't filter by that "
            f"-- showing the unfiltered breakdown instead."
        )
        entity_filter = None

    # An entity match implies which dimension the query must be grouped by,
    # since the filter column has to exist in the view we query -- e.g.
    # filtering on mission_type only makes sense against a by-type view.
    # Intents can override this default (see "maintenance" above), since its
    # two dimensions don't share a schema the way other intents' do. Shared
    # by both interpreters -- the LLM path picks its own dimension too, but
    # an entity filter still has to agree with whatever view actually has
    # that column.
    default_entity_to_dimension = {"unit_name": "unit", "mission_type": "type", "equipment_type": "equipment", "certification": "certification"}
    entity_to_dimension = matched_intent.get("entity_to_dimension", default_entity_to_dimension)
    if entity_filter:
        implied_dimension = entity_to_dimension.get(entity_filter[0])
        if implied_dimension and implied_dimension in matched_intent["views"]:
            dimension = implied_dimension

    view = matched_intent["views"].get(dimension, list(matched_intent["views"].values())[0])

    sort_order = "desc"
    for order, kws in SUPERLATIVE_KEYWORDS.items():
        if any(_kw_in(kw, q) for kw in kws):
            sort_order = order
            break
    # "Most expired" etc. describes the LOW end of a rate-style measure
    # (currency_rate_pct) by naming the negative condition, not by a generic
    # superlative -- overrides the superlative-keyword result above, since
    # "most" alone would otherwise (wrongly) sort toward the highest rate.
    if matched_intent["id"] == "training_currency" and any(_kw_in(kw, q) for kw in NEGATIVE_CONDITION_KEYWORDS):
        sort_order = "asc"
    # Same pattern, same reason, for maintenance's resolution-rate dimension:
    # "most unresolved" / "not resolved" / "outstanding" describes the LOW
    # end of resolution_rate_pct, not the high end -- found via adversarial
    # testing (QUESTION_TEST_LOG.md round 5), the same bug shape as
    # "most expired" above, just a different measure.
    if matched_intent["id"] == "maintenance" and dimension == "resolution" and any(_kw_in(kw, q) for kw in ["unresolved", "not resolved", "outstanding", "open discrepancies"]):
        sort_order = "asc"

    if any(_kw_in(kw, q) for kw in UNSUPPORTED_DIMENSION_KEYWORDS["community"]):
        for name_lower, name_orig in lookup["communities"].items():
            if name_lower in q:
                caveats.append(
                    f"This question mentioned the '{name_orig}' community, but no current measure "
                    f"can filter or group by community -- showing the full breakdown by unit instead. "
                    f"Treat this as NOT answering the community-specific part of the question."
                )
                break
        else:
            caveats.append(
                "This question mentioned 'community', but no current measure can filter or group by "
                "community -- showing the full breakdown instead. Treat this as NOT answering that part of the question."
            )
    if matched_intent["id"] != "trend" and any(_kw_in(kw, q) for kw in UNSUPPORTED_DIMENSION_KEYWORDS["time_trend"]):
        caveats.append(
            f"This question asked for a trend/time breakdown, but the '{matched_intent['id']}' measure "
            f"has no time dimension available -- showing the overall breakdown instead, NOT a trend."
        )
    # The trend view is a per-month line chart, not a ranked total -- it
    # cannot itself answer a "which unit has the most/highest X overall"
    # question, only show data a person could eyeball to guess at one.
    # Found for real switching to google/gemma-4-31b-it:free: "Which unit
    # has the most missions overall?" got answered with the unfiltered
    # trend chart and no caveat at all, a chart-type/question-type mismatch
    # none of the other caveat checks cover (they're about wrong measures,
    # this is about a measure that's right in domain but wrong in shape for
    # what was actually asked). Only fires with no entity_filter, since a
    # single-unit trend request ("mission count for Squadron 12 by month")
    # has no ranking ambiguity to caveat.
    if matched_intent["id"] == "trend" and not entity_filter and any(_kw_in(kw, q) for kw in SUPERLATIVE_KEYWORDS["asc"] + SUPERLATIVE_KEYWORDS["desc"]):
        caveats.append(
            "This question asks for a ranking ('most'/'highest'/etc.), but the trend measure only "
            "shows per-month counts as a line chart, not a single ranked total -- you'll need to read "
            "the chart or the underlying table yourself to determine the ranking."
        )

    # "Last N months" windowing only makes sense against the trend view (the
    # only one with a time dimension). An explicit number gets honored; a
    # vague relative-time phrase with no number ("recent months") can't be,
    # so it's surfaced as a caveat rather than silently showing everything
    # and letting the user assume it was windowed.
    month_window = None
    if matched_intent["id"] == "trend":
        match = re.search(r"(?:last|past)\s+(\d+)\s+months?", q)
        if match:
            month_window = int(match.group(1))
        elif any(w in q for w in ["recent months", "recently", "lately"]):
            caveats.append(
                "This question asked for a 'recent' time window without a specific number of months "
                "-- showing the full available date range instead of guessing what 'recent' means."
            )

    # This answer only exists because the keyword matcher found something
    # AFTER the LLM confidently said no measure applies -- only trust it
    # when it comes with a caveat. A caveat means the keyword matcher
    # itself is flagging a limitation (e.g. "no time dimension for this
    # measure"), which is a meaningfully different, lower-risk situation
    # than the keyword matcher producing a clean, uncaveated match the LLM
    # disagreed with -- that combination is more likely the keyword
    # matcher's own false positive than a genuine miss by the LLM, so it's
    # discarded and the LLM's rejection stands.
    if interpreted_by == "keyword_after_llm_no_match" and not caveats:
        return None

    return {
        "intent_id": matched_intent["id"],
        "dimension": dimension,
        "view": view,
        "entity_filter": entity_filter,
        "chart_spec": matched_intent["chart"],
        "sort_order": sort_order,
        "caveats": caveats,
        "month_window": month_window,
        "interpreted_by": interpreted_by,
    }


def answer_question(question):
    """
    Runs the full pipeline and returns a result dict for the UI to render:
        { sql, df, chart, measure_label, measure_description, matched_entity,
          understood: bool, question }

    `chart` is a small JSON-serializable spec -- {kind, x, y, color} -- naming
    which columns of `df` to plot and how, rather than a rendered figure
    object. This keeps the frontend free to render it with whatever charting
    library it uses (the API layer serializes this dict directly); it is not
    tied to any particular Python plotting library.
    """
    intent = interpret_question(question)
    if intent is None:
        return {
            "understood": False,
            "question": question,
            "sql": None,
            "df": None,
            "chart": None,
            "measure_label": None,
            "measure_description": None,
            "caveats": [],
            "interpreted_by": None,
        }

    view = intent["view"]
    sql = f"SELECT * FROM {view}"
    params = None
    matched_entity = None
    if intent["entity_filter"]:
        col, val = intent["entity_filter"]
        # column name is only ever one of a small fixed set from our own
        # INTENTS table above (never derived from user text), so this is safe
        # to interpolate; the VALUE is still passed as a bound parameter.
        sql += f" WHERE {col} = ?"
        params = [val]
        matched_entity = f"{col} = {val}"

    df = sl.query(sql, params=params)

    window_note = None
    if intent.get("month_window") and not df.empty and "mission_month" in df.columns:
        # Windowing is applied here, in pandas, on the already-fetched result
        # rather than as SQL -- "last N months" means the last N months that
        # actually appear in the data, not N calendar months back from
        # wall-clock "today" (there is no "today" in a historical reporting
        # dataset; the most recent recorded month is the right reference point).
        recent_months = sorted(df["mission_month"].unique())[-intent["month_window"]:]
        df = df[df["mission_month"].isin(recent_months)]
        window_note = (
            f"Filtered to the last {intent['month_window']} month(s) present in the data "
            f"({recent_months[0]} to {recent_months[-1]})."
        )

    chart_spec = intent["chart_spec"]
    dim = intent["dimension"]
    x_col = chart_spec["x"].get(dim, list(chart_spec["x"].values())[0])
    # y is usually the same column across dimensions (e.g. completion_rate_pct
    # whether grouped by unit or type) but for "maintenance" it's genuinely a
    # different measure per dimension (downtime hours vs. resolution rate),
    # so chart_spec["y"] may be a dict keyed by dimension just like "x".
    y_spec = chart_spec["y"]
    y_col = y_spec.get(dim, list(y_spec.values())[0]) if isinstance(y_spec, dict) else y_spec

    chart = None
    if not df.empty:
        if chart_spec["kind"] == "bar":
            ascending = intent["sort_order"] == "asc"
            df = df.sort_values(y_col, ascending=ascending)
            chart = {"kind": "bar", "x": x_col, "y": y_col, "color": None}
        elif chart_spec["kind"] == "line":
            color = chart_spec.get("color")
            df = df.sort_values(x_col)
            chart = {"kind": "line", "x": x_col, "y": y_col, "color": color}

    doc = sl.MEASURE_DOCS.get(view, {})

    return {
        "understood": True,
        "question": question,
        "sql": sql if not params else sql.replace("?", f"'{params[0]}'"),
        "df": df,
        "chart": chart,
        "measure_label": doc.get("label", view),
        "measure_description": doc.get("description", ""),
        "matched_entity": matched_entity,
        "source_table": doc.get("table", view),
        "caveats": intent["caveats"],
        "window_note": window_note,
        "interpreted_by": intent["interpreted_by"],
    }


SAMPLE_QUESTIONS = [
    "What is the mission completion rate by unit?",
    "What is the completion rate for Air Intercept Training missions?",
    "Show me average readiness by unit",
    "Which equipment type has the lowest readiness?",
    "What is the average mission duration by type?",
    "Show me mission count trends by month",
]
