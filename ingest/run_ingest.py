"""
Multimodal ingestion pipeline: text, audio, and imagery -> governed tables.

Runs the three unstructured sources through their extractors and writes
cleaned tables into data/clean/ alongside everything pipeline/clean.py
produces, so the semantic layer sees one uniform set of inputs and doesn't
know or care which of its tables came from a CSV and which came from a
photograph.

Two properties are deliberate and worth stating, because they're what makes
this more than a demo:

1. EVERY EXTRACTED ROW CARRIES ITS PROVENANCE -- source modality, source
   file, and which extractor produced it (LLM, deterministic rules, or OCR).
   A number on a dashboard that came from a transcribed audio recording is a
   weaker claim than one typed into a database, and an analyst has to be
   able to see that difference rather than infer it.

2. ACCURACY IS MEASURED, NOT ASSERTED. Every extraction is scored against
   the held-out ground truth in the manifests (which no extractor sees) and
   written to extraction_accuracy.json. Extraction quality is the whole
   basis for trusting downstream analytics, so an unmeasured extractor is an
   unquantified risk sitting underneath every chart built on top of it.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from ingest import extract_image, extract_text, transcribe_audio

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
CLEAN_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "clean")

log_entries = []


def log(table, action, count, reason):
    log_entries.append({
        "table": table, "action": action, "row_count": int(count), "reason": reason,
    })


def _score(records, truth_by_key, key_field, field_pairs):
    """
    Score extracted records against held-out truth.

    Reports `wrong` and `missing` separately rather than as one error rate,
    because they are not equally bad and averaging them hides that. A missing
    value is a visible gap an analyst can act on; a wrong value is a
    confident falsehood that propagates into a measure silently. A system
    that fails toward "missing" is behaving correctly under uncertainty.
    """
    stats = {f: {"correct": 0, "wrong": 0, "missing": 0} for f, _ in field_pairs}
    scored = 0
    for rec in records:
        truth = truth_by_key.get(rec.get(key_field))
        if truth is None:
            continue
        scored += 1
        for field, truth_field in field_pairs:
            got, want = rec.get(field), truth.get(truth_field)
            if got == want:
                stats[field]["correct"] += 1
            elif got is None:
                stats[field]["missing"] += 1
            else:
                stats[field]["wrong"] += 1

    total = sum(s["correct"] for s in stats.values())
    denom = scored * len(field_pairs)
    return {
        "records_scored": scored,
        "fields_per_record": len(field_pairs),
        "field_accuracy_pct": round(100.0 * total / denom, 1) if denom else None,
        "per_field": stats,
    }


def ingest_text():
    """Free-text debrief narratives -> structured records."""
    manifest_path = os.path.join(RAW_DIR, "debrief_manifest.json")
    if not os.path.exists(manifest_path):
        print("  (no debrief manifest; run data/generate_multimodal_data.py first)")
        return [], None

    with open(manifest_path) as f:
        manifest = json.load(f)

    records = []
    for entry in manifest:
        with open(os.path.join(RAW_DIR, entry["source_file"])) as fh:
            narrative = fh.read().strip()

        result = extract_text.extract(narrative)
        records.append({
            "debrief_id": entry["debrief_id"],
            "mission_id": entry["mission_id"],
            "unit_id": entry["unit_id"],
            "source_modality": "text",
            "source_file": entry["source_file"],
            "has_discrepancy": result["has_discrepancy"],
            "equipment_type": result["equipment_type"],
            "severity": result["severity"],
            "phase": result["phase"],
            "extracted_by": result["extracted_by"],
            "transcript_confidence": None,
        })

    truth = {e["debrief_id"]: e for e in manifest}
    accuracy = _score(records, truth, "debrief_id", [
        ("has_discrepancy", "truth_has_discrepancy"),
        ("equipment_type", "truth_equipment_type"),
        ("severity", "truth_severity"),
        ("phase", "truth_phase"),
    ])

    by_extractor = {}
    for r in records:
        by_extractor[r["extracted_by"]] = by_extractor.get(r["extracted_by"], 0) + 1
    log("debrief_extractions", "extract_from_text", len(records),
        f"Structured facts extracted from free-text debriefs; extractor mix: {by_extractor}")

    return records, accuracy


def ingest_audio():
    """
    Spoken debriefs -> transcript -> the SAME text extractor.

    Scored against the same ground truth as the typed narratives, which is
    what makes the comparison meaningful: any accuracy gap between this and
    ingest_text() is attributable to transcription, since everything after
    the transcript is identical code.
    """
    audio_dir = os.path.join(RAW_DIR, "debrief_audio")
    manifest_path = os.path.join(RAW_DIR, "debrief_manifest.json")
    if not os.path.isdir(audio_dir) or not os.path.exists(manifest_path):
        print("  (no audio corpus; skipping)")
        return [], None
    if not transcribe_audio.is_available():
        print("  (faster-whisper not installed; audio path skipped)")
        return [], None

    with open(manifest_path) as f:
        manifest = {e["debrief_id"]: e for e in json.load(f)}

    records = []
    for fname in sorted(os.listdir(audio_dir)):
        if not fname.endswith(".wav"):
            continue
        debrief_id = fname[:-4]
        entry = manifest.get(debrief_id)
        if entry is None:
            continue

        transcript, meta = transcribe_audio.transcribe(os.path.join(audio_dir, fname))
        if transcript is None:
            continue

        result = extract_text.extract(transcript)
        records.append({
            "debrief_id": debrief_id + "-AUD",
            "mission_id": entry["mission_id"],
            "unit_id": entry["unit_id"],
            "source_modality": "audio",
            "source_file": f"debrief_audio/{fname}",
            "has_discrepancy": result["has_discrepancy"],
            "equipment_type": result["equipment_type"],
            "severity": result["severity"],
            "phase": result["phase"],
            "extracted_by": result["extracted_by"],
            "transcript_confidence": meta.get("avg_logprob"),
        })

    truth = {e["debrief_id"] + "-AUD": e for e in manifest.values()}
    accuracy = _score(records, truth, "debrief_id", [
        ("has_discrepancy", "truth_has_discrepancy"),
        ("equipment_type", "truth_equipment_type"),
        ("severity", "truth_severity"),
        ("phase", "truth_phase"),
    ])
    log("debrief_extractions", "extract_from_audio", len(records),
        "Spoken debriefs transcribed (faster-whisper) then passed through the "
        "same text extractor as typed narratives")

    return records, accuracy


def ingest_images():
    """Photographed maintenance forms -> structured records."""
    form_dir = os.path.join(RAW_DIR, "forms")
    manifest_path = os.path.join(RAW_DIR, "form_manifest.json")
    if not os.path.isdir(form_dir) or not os.path.exists(manifest_path):
        print("  (no form corpus; skipping)")
        return [], None
    if not extract_image.is_available():
        print("  (tesseract not available; image path skipped)")
        return [], None

    with open(manifest_path) as f:
        manifest = json.load(f)

    records = []
    for entry in manifest:
        fields, meta = extract_image.extract(os.path.join(RAW_DIR, entry["source_file"]))
        if fields is None:
            continue
        records.append({
            "form_id": entry["form_id"],  # filename identity, not OCR-derived
            "ocr_form_id": fields["form_id"],
            "unit_id": fields["unit_id"],
            "equipment_type": fields["equipment_type"],
            "severity": fields["severity"],
            "downtime_hours": fields["downtime_hours"],
            "resolved": fields["resolved"],
            "source_modality": "image",
            "source_file": entry["source_file"],
            "extracted_by": fields["extracted_by"],
            "ocr_mean_confidence": meta.get("mean_confidence"),
        })

    truth = {e["form_id"]: e for e in manifest}
    accuracy = _score(records, truth, "form_id", [
        ("unit_id", "truth_unit_id"),
        ("equipment_type", "truth_equipment_type"),
        ("severity", "truth_severity"),
        ("downtime_hours", "truth_downtime_hours"),
        ("resolved", "truth_resolved"),
    ])
    log("form_extractions", "extract_from_image", len(records),
        "Fields recovered from photographed maintenance discrepancy forms via "
        "layout-aware OCR (tesseract)")

    return records, accuracy


def main():
    os.makedirs(CLEAN_DIR, exist_ok=True)
    print("Multimodal ingestion: text, audio, imagery -> governed tables\n")

    print("text  ...")
    text_records, text_acc = ingest_text()
    print(f"  {len(text_records)} debrief narratives")

    print("audio ...")
    audio_records, audio_acc = ingest_audio()
    print(f"  {len(audio_records)} spoken debriefs")

    print("image ...")
    image_records, image_acc = ingest_images()
    print(f"  {len(image_records)} photographed forms")

    debriefs = text_records + audio_records
    if debriefs:
        pd.DataFrame(debriefs).to_csv(
            os.path.join(CLEAN_DIR, "debrief_extractions.csv"), index=False)
    if image_records:
        pd.DataFrame(image_records).to_csv(
            os.path.join(CLEAN_DIR, "form_extractions.csv"), index=False)

    accuracy = {
        "text": text_acc,
        "audio": audio_acc,
        "image": image_acc,
        "note": (
            "Scored against held-out ground truth in data/raw/*_manifest.json, "
            "which no extractor reads. 'wrong' and 'missing' are reported "
            "separately on purpose: a missing value is a visible gap, a wrong "
            "value is a silent error, and they carry very different risk."
        ),
    }
    with open(os.path.join(CLEAN_DIR, "extraction_accuracy.json"), "w") as f:
        json.dump(accuracy, f, indent=2)

    with open(os.path.join(CLEAN_DIR, "multimodal_ingestion_log.json"), "w") as f:
        json.dump(log_entries, f, indent=2)

    print("\nExtraction accuracy vs. held-out ground truth:")
    for modality, acc in (("text", text_acc), ("audio", audio_acc), ("image", image_acc)):
        if not acc:
            continue
        print(f"  {modality:6s} {acc['field_accuracy_pct']:5.1f}% "
              f"({acc['records_scored']} records x {acc['fields_per_record']} fields)")
        for field, s in acc["per_field"].items():
            print(f"      {field:20s} ok={s['correct']:3d} wrong={s['wrong']:3d} missing={s['missing']:3d}")

    print(f"\nWrote data/clean/debrief_extractions.csv, form_extractions.csv, "
          f"extraction_accuracy.json")


if __name__ == "__main__":
    main()
