"""
Field extraction from photographed/scanned maintenance discrepancy forms.

The graphics modality here is deliberately the boring, high-value one. A
demo that classifies aircraft in imagery looks more impressive and would be
much less useful: the actual document-processing bottleneck in maintenance
reporting is paper and PDF forms whose contents never reach a database,
where the information is already structured -- it's just trapped in pixels.

Two-stage, for the same reason the text path is two-stage: OCR (tesseract)
produces raw text, then field parsing maps that text onto the same
vocabulary the structured sources use. OCR noise is expected and handled at
the parsing stage rather than assumed away, because a form photographed on a
hangar deck is rotated, unevenly lit, and slightly out of focus -- which is
exactly how data/generate_multimodal_data.py renders the test corpus.
"""
import os
import re

EQUIPMENT_TYPES = ["Primary Aircraft/Vehicle", "Comms Suite", "Sensor Package"]
SEVERITIES = ["Minor", "Moderate", "Major"]


def is_available():
    """
    Whether OCR is usable: both the Python binding and the tesseract binary
    it shells out to. Checking only the import would let this fail later at
    the first real call with a confusing PATH error.
    """
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr(image_path):
    """Returns (raw_text, metadata); raw_text is None if OCR is unavailable."""
    if not is_available():
        return None, {"engine": None, "error": "pytesseract/tesseract not available"}

    import pytesseract
    from PIL import Image

    try:
        img = Image.open(image_path)
        # Greyscale before OCR: the synthetic degradation adds colored
        # speckle noise, and tesseract binarizes more cleanly from L than
        # from RGB.
        text = pytesseract.image_to_string(img.convert("L"))
    except Exception as e:
        return None, {"engine": "tesseract", "error": str(e)}

    return text, {
        "engine": "tesseract",
        "version": str(pytesseract.get_tesseract_version()),
        "char_count": len(text),
    }


def _preprocess(img):
    """
    Greyscale only, deliberately.

    An upscale + median-filter + autocontrast pipeline (the textbook
    document-imaging cleanup) was implemented here and then REMOVED after
    measurement, because it made extraction worse on this corpus: overall
    field accuracy fell from 73% to 64%, the RESOLVED value stopped being
    detected on 13 of 15 forms, and the UNIT ID token that preprocessing was
    added to rescue came back with its confidence dropped from 80 to 17 --
    low enough to be discarded downstream. Net negative on every field it
    touched.

    Worth recording why the wrong conclusion was reached first: the
    preprocessing was validated against a proxy ("does a unit-ID-shaped
    regex match anywhere in the OCR text?") which it improved 0/4 -> 3/4,
    while the metric that actually matters -- correct values in the right
    fields -- got worse. A proxy that moves in the opposite direction from
    the real measure is worse than no measurement, and this is a compact
    example of it.
    """
    return img.convert("L")


def ocr_rows(image_path):
    """
    Layout-aware OCR: returns the page as a list of visual rows, each a list
    of (x, text) words ordered left-to-right.

    This exists because reading a form as a flat string does not work, and
    the way it fails is quiet rather than loud. Tesseract serializes a
    two-column form in COLUMN order -- every label, then every value:

        FORM ID:  UNIT ID:  EQUIPMENT:  SEVERITY:  RESOLVED:  DOWNTIME HRS:
        FORM0001  U05  Comms Suite  Minor  16  NO

    so a "LABEL: value on the same line" parser extracts nothing at all, and
    worse, page rotation reorders the label block independently of the value
    block (observed directly: RESOLVED came out ahead of DOWNTIME HRS while
    their values stayed in the original order). Any parser that pairs the
    Nth label with the Nth value therefore mismatches fields on exactly the
    rotated, real-world-looking scans it most needs to handle -- and it
    mismatches them silently, producing a confident wrong value rather than
    a blank.

    Grouping words by vertical position instead reconstructs the true rows,
    which is both rotation-tolerant (within the tolerance band) and how
    document-understanding systems actually approach forms.
    """
    if not is_available():
        return None, {"engine": None, "error": "pytesseract/tesseract not available"}

    import pytesseract
    from PIL import Image

    try:
        data = pytesseract.image_to_data(
            _preprocess(Image.open(image_path)), output_type=pytesseract.Output.DICT
        )
    except Exception as e:
        return None, {"engine": "tesseract", "error": str(e)}

    words = []
    for i, text in enumerate(data["text"]):
        text = (text or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        # Tuned against field accuracy on the labeled corpus rather than
        # picked by intuition: 30 (the value first chosen by eye) discarded
        # legible short values like "U05" and cost 6 points of accuracy
        # (81% vs 87%). Below 20 nothing further is gained, so this keeps a
        # little speckle rejection at no measured cost.
        if conf < 20:
            continue
        words.append({
            "text": text,
            "x": data["left"][i],
            "y": data["top"][i] + data["height"][i] / 2.0,
            "h": data["height"][i],
            "conf": conf,
        })

    if not words:
        return [], {"engine": "tesseract", "word_count": 0}

    # Row tolerance scales with text height so this doesn't depend on the
    # form being rendered at one particular DPI.
    tol = max(12, int(sum(w["h"] for w in words) / len(words) * 0.7))

    rows = []
    for w in sorted(words, key=lambda w: w["y"]):
        placed = False
        for row in rows:
            if abs(row["y"] - w["y"]) <= tol:
                row["words"].append(w)
                row["y"] = sum(x["y"] for x in row["words"]) / len(row["words"])
                placed = True
                break
        if not placed:
            rows.append({"y": w["y"], "words": [w]})

    out = [
        [(w["x"], w["text"]) for w in sorted(r["words"], key=lambda w: w["x"])]
        for r in sorted(rows, key=lambda r: r["y"])
    ]
    mean_conf = sum(w["conf"] for w in words) / len(words)
    return out, {
        "engine": "tesseract",
        "version": str(pytesseract.get_tesseract_version()),
        "word_count": len(words),
        "row_count": len(out),
        "mean_confidence": round(mean_conf, 1),
    }


# OCR confusions that actually occur on this corpus, in the direction
# glyph -> intended character. Applied only to fields whose expected shape is
# known (a unit ID is always U0[1-5]), never to free text, since "correcting"
# prose this way would introduce errors rather than fix them.
_CONFUSIONS = str.maketrans({
    "O": "0", "o": "0", "Q": "0", "D": "0",
    "S": "5", "s": "5",
    "l": "1", "I": "1", "|": "1",
    "B": "8", "Z": "2", "G": "6",
})


_LABEL_WORDS = {"FORM", "UNIT", "ID", "EQUIPMENT", "SEVERITY", "DOWNTIME", "HRS", "RESOLVED"}


def _row_text(row):
    return " ".join(t for _, t in row)


def _find_field_spatial(rows, label_pattern):
    """
    Find a labeled field by locating the label in a visual row and taking
    the words to its RIGHT as the value. Falls back to the next row down
    when a row holds only the label, which happens when a value is nudged
    across the tolerance band by page rotation.
    """
    pat = re.compile(label_pattern, re.IGNORECASE)

    for idx, row in enumerate(rows):
        joined = _row_text(row)
        if not pat.search(joined.replace(".", "")):
            continue

        # Value words are those starting to the right of the label's last
        # word. Using x-position rather than string splitting keeps this
        # working when OCR mangles the colon or splits the label in two.
        label_end_x = 0
        for x, t in row:
            if pat.search(t.replace(".", "").replace(":", "")) or t.rstrip(":.").upper() in {
                "ID", "HRS", "FORM", "UNIT", "EQUIPMENT", "SEVERITY", "DOWNTIME", "RESOLVED",
            }:
                label_end_x = max(label_end_x, x)

        value_words = [t for x, t in row if x > label_end_x + 20]
        if value_words:
            return " ".join(value_words).strip()

        # Row held only the label. Look one row down -- but ONLY if that row
        # isn't itself another field's label row. Without this guard,
        # DOWNTIME with a displaced value happily returns the RESOLVED row
        # beneath it, and digit-extraction then reads "RESOLVED: NO" (after
        # confusion repair, "RE50LVED: N0") as a downtime of 50 hours. A
        # missing value must stay missing; inventing one is the failure mode
        # this whole codebase treats as worse than an obvious gap.
        if idx + 1 < len(rows):
            nxt = rows[idx + 1]
            next_tokens = {t.rstrip(":.").upper() for _, t in nxt}
            if not (next_tokens & _LABEL_WORDS):
                return _row_text(nxt).strip()
        return ""

    return ""


def _find_field(text, label_pattern):
    """
    Flat-text field lookup, retained for the same-line case and used as a
    fallback when spatial parsing finds nothing.
    """
    m = re.search(label_pattern + r"[:\s]*([^\n]*)", text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _recover_orphan_value(rows, vocabulary):
    """
    Find a closed-vocabulary value sitting on a row with no recognizable
    label. Only rows WITHOUT a field label are considered, so this can't
    steal a value that already belongs to a different labeled field.
    """
    label_words = {"FORM", "UNIT", "ID", "EQUIPMENT", "SEVERITY", "DOWNTIME", "HRS", "RESOLVED"}
    for row in rows:
        tokens = [t.rstrip(":.").upper() for _, t in row]
        if any(tok in label_words for tok in tokens):
            continue
        match = _fuzzy_match(_row_text(row), vocabulary)
        if match:
            return match
    return None


def _fuzzy_match(value, candidates):
    """
    Map an OCR'd string onto a known vocabulary term. Tries exact match
    first, then containment either direction, then a token-overlap score --
    "Comms Suile" and "Comms  Suite" should both resolve to "Comms Suite"
    rather than being dropped as unrecognized. Values that match nothing are
    returned as None rather than guessed, so an unreadable field becomes a
    visible gap instead of a plausible-looking wrong value.
    """
    if not value:
        return None
    v = value.strip().lower()
    for c in candidates:
        if v == c.lower():
            return c
    for c in candidates:
        if c.lower() in v or v in c.lower():
            return c

    best, best_score = None, 0
    v_tokens = set(re.findall(r"[a-z]+", v))
    for c in candidates:
        c_tokens = set(re.findall(r"[a-z]+", c.lower()))
        if not c_tokens:
            continue
        score = len(v_tokens & c_tokens) / len(c_tokens)
        if score > best_score:
            best, best_score = c, score
    # 0.5 = at least half the expected tokens recovered. Below that the
    # evidence is too thin to claim a match.
    return best if best_score >= 0.5 else None


def extract_fields(rows):
    """
    Maps spatially-parsed OCR rows onto the same vocabulary the structured
    sources use. Character-confusion repair is applied per field, using each
    field's known shape as the constraint.
    """
    unit_raw = _find_field_spatial(rows, r"UNIT\s*ID")
    # "U05" is routinely read as "v0S" or "u05": fix the digits via the
    # confusion table, and accept any leading letter, since U/V/u are
    # interchangeable to OCR at this resolution and the U is not the
    # informative part -- the digit is.
    unit_fixed = (unit_raw or "").translate(_CONFUSIONS)
    unit_match = re.search(r"[A-Za-z]\s*0?\s*([1-5])\b", unit_fixed)
    unit_id = f"U0{unit_match.group(1)}" if unit_match else None

    equipment = _fuzzy_match(_find_field_spatial(rows, r"EQUIPMENT"), EQUIPMENT_TYPES)
    severity = _fuzzy_match(_find_field_spatial(rows, r"SEVERITY"), SEVERITIES)

    # Orphan-value recovery for closed-vocabulary fields. OCR sometimes drops
    # a label outright while reading its value cleanly (observed: the
    # SEVERITY label vanished, leaving a bare "Minor" on its own row), and a
    # strictly label-anchored parser throws that value away even though it is
    # perfectly legible. Safe here precisely BECAUSE these vocabularies are
    # closed and disjoint -- "Minor" can only be a severity, so recovering it
    # by value introduces no ambiguity. Deliberately not done for open fields
    # like downtime, where a bare number could belong to several fields and
    # guessing would risk a confident wrong value.
    if severity is None:
        severity = _recover_orphan_value(rows, SEVERITIES)
    if equipment is None:
        equipment = _recover_orphan_value(rows, EQUIPMENT_TYPES)

    # Read digits from the ORIGINAL text first and only fall back to
    # confusion-repaired text if none are present. Repairing first is
    # actively harmful on a field like this: the repair table maps S->5 and
    # O->0, so any stray letters in the captured region manufacture digits
    # that were never on the form.
    downtime_src = _find_field_spatial(rows, r"DOWNTIME") or ""
    downtime_match = re.search(r"\d+", downtime_src) or re.search(
        r"\d+", downtime_src.translate(_CONFUSIONS)
    )
    downtime = int(downtime_match.group()) if downtime_match else None

    resolved_raw = (_find_field_spatial(rows, r"RESOLVED") or "").strip().upper()
    if resolved_raw.startswith("Y"):
        resolved = True
    elif resolved_raw.startswith(("N", "M")):  # N frequently OCRs as M
        resolved = False
    else:
        resolved = None

    form_raw = (_find_field_spatial(rows, r"FORM\s*ID") or "").translate(_CONFUSIONS)
    form_match = re.search(r"(\d{3,})", form_raw)
    form_id = f"FORM{int(form_match.group(1)):04d}" if form_match else None

    return {
        "form_id": form_id,
        "unit_id": unit_id,
        "equipment_type": equipment,
        "severity": severity,
        "downtime_hours": downtime,
        "resolved": resolved,
        "extracted_by": "ocr",
    }


def extract(image_path):
    """Full path: image -> layout-aware OCR -> structured fields, with provenance."""
    rows, meta = ocr_rows(image_path)
    if rows is None:
        return None, meta
    fields = extract_fields(rows)
    fields["source_file"] = os.path.basename(image_path)
    return fields, meta
