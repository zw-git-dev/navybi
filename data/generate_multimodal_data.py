"""
Generates synthetic UNSTRUCTURED post-mission sources: free-text debrief
narratives, spoken-debrief audio, and photographed maintenance discrepancy
forms.

Why this exists separately from generate_synthetic_data.py: that script
produces structured records (CSV/JSON/SQLite) where the "hard part" is
cleansing. These three sources are hard for a different reason -- the
information isn't in fields at all, it's in prose, speech, and pixels, and
has to be extracted before it can be governed or measured. Keeping the two
generators separate makes that distinction legible rather than blurring
"messy structured data" together with "not structured at all."

GROUND TRUTH IS THE POINT. Every narrative and every form is generated FROM a
known set of facts (which equipment was affected, whether there was a
discrepancy at all, severity, mission phase), and those facts are written to
a separate manifest that the extractors never see. That's what makes
extraction accuracy measurable instead of assertable -- the same discipline
QUESTION_TEST_LOG.md applies to the conversational layer. Without held-out
labels, "our extraction works well" is an opinion.

This is fabricated data for prototype purposes only -- no real unit,
personnel, mission, or maintenance information.
"""
import json
import os
import random
import subprocess

RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")
DEBRIEF_DIR = os.path.join(RAW_DIR, "debriefs")
AUDIO_DIR = os.path.join(RAW_DIR, "debrief_audio")
FORM_DIR = os.path.join(RAW_DIR, "forms")

random.seed(1701)

# Deliberately the SAME equipment vocabulary as the readiness and maintenance
# sources. That conformed dimension is what lets a narrative-derived finding
# ("crews keep mentioning the Comms Suite") be compared against a
# structured-record finding ("the Comms Suite logged N maintenance events")
# instead of the two living in unrelated namespaces.
EQUIPMENT_TYPES = ["Primary Aircraft/Vehicle", "Comms Suite", "Sensor Package"]

UNIT_IDS = ["U01", "U02", "U03", "U04", "U05"]

PHASES = ["Preflight", "Ingress", "On-Station", "Egress", "Recovery"]
SEVERITIES = ["Minor", "Moderate", "Major"]

# Symptom phrasing per equipment type. Multiple phrasings per item on purpose:
# an extractor that only works because every narrative says the equipment's
# exact catalog name isn't demonstrating extraction, it's demonstrating string
# matching. Several of these never name the equipment directly ("the radar,"
# "comms") so the extractor has to map vocabulary, not just find a substring.
SYMPTOMS = {
    "Primary Aircraft/Vehicle": [
        "a hydraulic indication on the number two system",
        "an intermittent gear position warning",
        "unexpected airframe vibration above 300 knots",
        "a flight control trim anomaly",
    ],
    "Comms Suite": [
        "intermittent UHF dropouts",
        "degraded secure voice quality",
        "a total loss of datalink for roughly four minutes",
        "comms garbling on the primary freq",
    ],
    "Sensor Package": [
        "radar returns washing out at range",
        "an unstable FLIR gimbal",
        "the targeting pod failing to hand off",
        "sensor video breaking up intermittently",
    ],
}

CLEAN_CLOSERS = [
    "No discrepancies noted. Aircraft up on recovery.",
    "No gripes this sortie.",
    "Systems nominal throughout. Nothing to report on the maintenance side.",
    "All systems performed as advertised. No write-ups.",
]

OPENERS = [
    "Uneventful launch and departure.",
    "Brief and walk on time, normal start sequence.",
    "Crew briefed at 0600, on deck 0715.",
    "Standard preflight, no issues on the walkaround.",
    "Launched as fragged.",
]

# Light, realistic Navy-report messiness: abbreviations and casing drift that
# a real debrief typed in a hurry would have. Applied probabilistically so the
# corpus isn't uniformly messy or uniformly clean.
ABBREVIATIONS = [
    ("mission", "msn"), ("aircraft", "acft"), ("maintenance", "mx"),
    ("communications", "comms"), ("approximately", "approx"),
]


def _messy(text):
    """Apply occasional abbreviation and casing drift to a narrative."""
    for full, abbr in ABBREVIATIONS:
        if random.random() < 0.4:
            text = text.replace(full, abbr)
    if random.random() < 0.15:
        text = text.upper()  # the all-caps report, a real and annoying genre
    return text


def _build_narrative(has_discrepancy, equipment, severity, phase):
    """
    Compose a debrief narrative that ENCODES the given facts without ever
    stating them as labeled fields -- the extractor has to infer them from
    prose, which is the actual task being demonstrated.
    """
    parts = [random.choice(OPENERS)]

    if not has_discrepancy:
        parts.append(random.choice(CLEAN_CLOSERS))
        return _messy(" ".join(parts))

    symptom = random.choice(SYMPTOMS[equipment])
    severity_phrasing = {
        "Minor": [
            "Wrote it up as a minor gripe, no impact to the mission.",
            "Annoyance level only, mission continued as planned.",
            "Logged it but it did not affect the tasking.",
        ],
        "Moderate": [
            "Degraded our effectiveness for part of the event.",
            "Worked around it but it cost us time on station.",
            "Partial mission impact, recommend mx look at it before next go.",
        ],
        "Major": [
            "Knocked us off the tasking entirely, RTB early.",
            "Mission aborted, this needs maintenance attention immediately.",
            "Hard down on recovery, significant impact.",
        ],
    }[severity]

    parts.append(f"During {phase.lower()} we experienced {symptom}.")
    parts.append(random.choice(severity_phrasing))
    return _messy(" ".join(parts))


def generate_debriefs(count=60):
    """
    Writes one .txt per debrief plus a manifest carrying the linkage
    (mission/unit) and the held-out ground truth.
    """
    os.makedirs(DEBRIEF_DIR, exist_ok=True)
    manifest = []

    for i in range(1, count + 1):
        debrief_id = f"DB{i:04d}"
        # ~35% clean sorties: an extractor that always finds a discrepancy
        # would score well on a corpus where everything is broken, so the
        # negative cases are what make the accuracy number mean anything.
        has_discrepancy = random.random() > 0.35
        equipment = random.choice(EQUIPMENT_TYPES) if has_discrepancy else None
        severity = random.choice(SEVERITIES) if has_discrepancy else None
        phase = random.choice(PHASES) if has_discrepancy else None

        narrative = _build_narrative(has_discrepancy, equipment, severity, phase)

        path = os.path.join(DEBRIEF_DIR, f"{debrief_id}.txt")
        with open(path, "w") as f:
            f.write(narrative + "\n")

        manifest.append({
            "debrief_id": debrief_id,
            "mission_id": f"M{random.randint(1, 600):05d}",
            "unit_id": random.choice(UNIT_IDS),
            "source_file": f"debriefs/{debrief_id}.txt",
            "truth_has_discrepancy": has_discrepancy,
            "truth_equipment_type": equipment,
            "truth_severity": severity,
            "truth_phase": phase,
        })

    with open(os.path.join(RAW_DIR, "debrief_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def generate_audio(manifest, count=12):
    """
    Renders a subset of debriefs to spoken audio using macOS `say`, so the
    audio path can be exercised end-to-end on real waveforms rather than
    mocked. Uses several voices and speaking rates -- a transcriber that only
    works on one narrator isn't demonstrating anything transferable.

    Skipped gracefully off macOS; the audio ingestion path is then simply
    untested on that host rather than silently faked.
    """
    if not os.path.exists("/usr/bin/say"):
        print("  (skipping audio: macOS `say` not available on this host)")
        return []

    os.makedirs(AUDIO_DIR, exist_ok=True)
    voices = ["Alex", "Samantha", "Daniel"]
    produced = []

    for entry in manifest[:count]:
        debrief_id = entry["debrief_id"]
        with open(os.path.join(RAW_DIR, entry["source_file"])) as f:
            text = f.read().strip()

        aiff = os.path.join(AUDIO_DIR, f"{debrief_id}.aiff")
        wav = os.path.join(AUDIO_DIR, f"{debrief_id}.wav")

        subprocess.run(
            ["say", "-v", random.choice(voices), "-r", str(random.choice([160, 180, 200])),
             "-o", aiff, text],
            check=True,
        )
        # 16 kHz mono PCM is what speech recognizers expect; converting here
        # rather than at ingestion time keeps the corpus in one canonical form.
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", aiff, wav],
            check=True,
        )
        os.remove(aiff)
        produced.append(debrief_id)

    return produced


def generate_forms(count=15):
    """
    Renders synthetic maintenance discrepancy forms as images, then degrades
    them (rotation, blur, noise, uneven lighting) to approximate a form
    photographed on a hangar deck rather than a clean digital export. A clean
    render would make OCR look better than it has any right to.
    """
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    os.makedirs(FORM_DIR, exist_ok=True)
    manifest = []

    try:
        font_h = ImageFont.truetype("/System/Library/Fonts/Supplemental/Courier New Bold.ttf", 26)
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Courier New.ttf", 22)
    except OSError:
        font_h = font = ImageFont.load_default()

    for i in range(1, count + 1):
        form_id = f"FORM{i:04d}"
        unit_id = random.choice(UNIT_IDS)
        equipment = random.choice(EQUIPMENT_TYPES)
        severity = random.choice(SEVERITIES)
        downtime = random.choice([2, 4, 6, 8, 12, 16, 24, 48])
        resolved = random.choice(["YES", "NO"])

        img = Image.new("RGB", (900, 620), "white")
        d = ImageDraw.Draw(img)

        d.text((40, 30), "MAINTENANCE DISCREPANCY REPORT", font=font_h, fill="black")
        d.line([(40, 70), (860, 70)], fill="black", width=2)

        rows = [
            ("FORM ID:", form_id),
            ("UNIT ID:", unit_id),
            ("EQUIPMENT:", equipment),
            ("SEVERITY:", severity),
            ("DOWNTIME HRS:", str(downtime)),
            ("RESOLVED:", resolved),
        ]
        y = 110
        for label, value in rows:
            d.text((60, y), label, font=font, fill="black")
            d.text((340, y), value, font=font, fill="black")
            y += 58

        d.rectangle([(40, 90), (860, y + 10)], outline="black", width=2)

        # Degradation, in the order a real photo would acquire it: geometry
        # first (the form isn't square to the camera), then optics (focus),
        # then sensor noise.
        img = img.rotate(random.uniform(-1.8, 1.8), expand=False, fillcolor="white")
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.3, 0.8)))

        px = img.load()
        for _ in range(4000):
            x, yy = random.randint(0, img.width - 1), random.randint(0, img.height - 1)
            shade = random.randint(150, 210)
            px[x, yy] = (shade, shade, shade)

        img.save(os.path.join(FORM_DIR, f"{form_id}.png"))

        manifest.append({
            "form_id": form_id,
            "source_file": f"forms/{form_id}.png",
            "truth_unit_id": unit_id,
            "truth_equipment_type": equipment,
            "truth_severity": severity,
            "truth_downtime_hours": downtime,
            "truth_resolved": resolved == "YES",
        })

    with open(os.path.join(RAW_DIR, "form_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def main():
    print("Generating synthetic unstructured post-mission sources...")
    debriefs = generate_debriefs()
    print(f"  text:  {len(debriefs)} debrief narratives -> data/raw/debriefs/")

    audio = generate_audio(debriefs)
    print(f"  audio: {len(audio)} spoken debriefs -> data/raw/debrief_audio/")

    forms = generate_forms()
    print(f"  image: {len(forms)} photographed discrepancy forms -> data/raw/forms/")

    n_disc = sum(1 for d in debriefs if d["truth_has_discrepancy"])
    print(f"\nGround truth written to debrief_manifest.json / form_manifest.json")
    print(f"  {n_disc}/{len(debriefs)} debriefs describe a discrepancy "
          f"({len(debriefs) - n_disc} clean sorties as negative cases)")


if __name__ == "__main__":
    main()
