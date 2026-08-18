import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from cachetools import TTLCache
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_current_user
from api.utils import df_to_records
from app.llm_interpret import OPENROUTER_MODEL, is_configured
from app.nl_query import SAMPLE_QUESTIONS, answer_question
from auth import auth as auth_core

router = APIRouter(prefix="/api", tags=["ask"], dependencies=[Depends(get_current_user)])

# Caches answer_question() by normalized question text so asking the same
# question twice (a sample-question chip clicked again, two users asking
# the same thing, someone re-checking an earlier answer) doesn't re-spend
# an OpenRouter LLM call -- the real cost/latency driver in this pipeline.
# Keyed on question text alone: the answer never depends on who's asking,
# only on the question and the (process-lifetime-static) warehouse
# contents. A short TTL (rather than caching forever) bounds staleness if
# the warehouse is ever rebuilt without restarting the process, and bounds
# memory via maxsize. The audit log still records every request, cached or
# not -- caching only skips the recompute, not the "who asked what" trail.
_ask_cache = TTLCache(maxsize=256, ttl=600)
_ask_cache_lock = threading.Lock()


class AskRequest(BaseModel):
    question: str


@router.get("/ask/meta")
def ask_meta():
    return {"sample_questions": SAMPLE_QUESTIONS, "llm_configured": is_configured(), "llm_model": OPENROUTER_MODEL}


@router.post("/ask")
def ask(body: AskRequest, user: dict = Depends(get_current_user)):
    cache_key = body.question.strip().lower()

    with _ask_cache_lock:
        result = _ask_cache.get(cache_key)

    if result is None:
        result = answer_question(body.question)
        with _ask_cache_lock:
            _ask_cache[cache_key] = result

    auth_core.log_query(
        username=user["username"],
        role=user["role"],
        question=body.question,
        understood=result["understood"],
        interpreted_by=result.get("interpreted_by"),
        caveat_count=len(result.get("caveats") or []),
    )

    response = dict(result)
    response["df"] = df_to_records(result["df"])
    return response
