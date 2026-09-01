"""
Speech-to-text for spoken post-mission debriefs.

The architectural point of this module is what it DOESN'T do: it does not
extract any facts. It converts audio to text and hands off to
ingest/extract_text.py -- the exact same extractor the typed-narrative path
uses. Audio converges into the text pipeline rather than running alongside
it.

That matters for more than tidiness. A parallel audio-specific extractor
would be a second place where "what counts as a Major discrepancy" is
decided, and those two definitions would drift -- which is the same class of
problem warehouse/semantic_layer.py::MEASURE_DOCS exists to prevent for SQL
and DAX. One extractor means a spoken debrief and a typed debrief describing
the same sortie produce the same structured record, and any improvement to
extraction benefits both modalities at once.

Transcription uses faster-whisper (an optimized reimplementation of OpenAI's
Whisper). The model is downloaded on first use and cached locally; "base" is
the default as a deliberate accuracy/footprint tradeoff for a prototype
running on a laptop, overridable via NAVYBI_WHISPER_MODEL.
"""
import os

WHISPER_MODEL_SIZE = os.environ.get("NAVYBI_WHISPER_MODEL", "base")

_model = None


def is_available():
    """
    Whether the speech-to-text dependency is installed. Kept optional on
    purpose -- faster-whisper pulls in a substantial native runtime, and the
    core BI application has no reason to carry it. Callers degrade to
    "audio not ingested" rather than failing, the same way the app degrades
    to the keyword matcher without an LLM key.
    """
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _get_model():
    """Loaded once and reused -- model load dominates per-file cost."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        # int8 on CPU: this runs on developer laptops and CI runners, not GPUs.
        _model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def transcribe(audio_path):
    """
    Returns (transcript, metadata) or (None, metadata) if unavailable.

    metadata carries the provenance the audit trail needs: which engine and
    model produced this text, and the model's own confidence. Downstream, a
    fact extracted from a low-confidence transcript is a materially weaker
    claim than one extracted from typed text, and the record should be able
    to say so rather than presenting both as equally solid.
    """
    if not is_available():
        return None, {"engine": None, "error": "faster-whisper not installed"}

    try:
        segments, info = _get_model().transcribe(audio_path, beam_size=5, language="en")
        segments = list(segments)
    except Exception as e:
        return None, {"engine": "faster-whisper", "error": str(e)}

    transcript = " ".join(s.text.strip() for s in segments).strip()

    # avg_logprob is per-segment; averaging gives a rough document-level
    # confidence. Reported as-is rather than mapped to a friendly 0-100
    # score, because inventing a scale would imply calibration this hasn't
    # been checked for.
    avg_logprob = (
        sum(s.avg_logprob for s in segments) / len(segments) if segments else None
    )

    return transcript, {
        "engine": "faster-whisper",
        "model": WHISPER_MODEL_SIZE,
        "language": info.language,
        "duration_seconds": round(info.duration, 2),
        "avg_logprob": round(avg_logprob, 3) if avg_logprob is not None else None,
        "segment_count": len(segments),
    }
