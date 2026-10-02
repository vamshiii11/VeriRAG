import copy, hashlib, json, re, httpx, logging
from collections import OrderedDict
from threading import Lock
from .config import settings

logger=logging.getLogger(__name__)
_result_cache=OrderedDict()
_result_cache_lock=Lock()
_inflight_calls={}


def _cached_call(namespace,payload,callback):
    config=(settings.llm_provider,settings.llm_model,settings.llm_base_url,hashlib.sha256(settings.llm_api_key.encode()).hexdigest())
    cache_key=hashlib.sha256(json.dumps([namespace,config,payload],sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
    with _result_cache_lock:
        if cache_key in _result_cache:
            _result_cache.move_to_end(cache_key)
            return copy.deepcopy(_result_cache[cache_key])
        call_lock=_inflight_calls.setdefault(cache_key,Lock())
    try:
        with call_lock:
            with _result_cache_lock:
                if cache_key in _result_cache:
                    _result_cache.move_to_end(cache_key)
                    return copy.deepcopy(_result_cache[cache_key])
            result=callback()
            with _result_cache_lock:
                _result_cache[cache_key]=copy.deepcopy(result)
                _result_cache.move_to_end(cache_key)
                while len(_result_cache)>128:
                    _result_cache.popitem(last=False)
            return copy.deepcopy(result)
    finally:
        with _result_cache_lock:
            if _inflight_calls.get(cache_key) is call_lock:
                _inflight_calls.pop(cache_key,None)

SYSTEM = """You are VeriRAG, an evidence-grounded enterprise assistant. Use ONLY the supplied evidence.
Never invent policy facts. If evidence is insufficient, say so. Distinguish explicit evidence from inference.
Return valid JSON with keys: answer, claims, missing_information.
claims must be an array of short factual statements. Do not add unsupported claims."""

def generate(question,evidence):
    return _cached_call("answer",{"question":question,"evidence":evidence},lambda:_generate_uncached(question,evidence))


def _generate_uncached(question,evidence):
    context="\n\n".join([f"[EVIDENCE {i+1}] {e['document']} version {e.get('version','unknown')} effective {e.get('effective_date','unknown')} page {e['page']} temporal_status={e.get('temporal_status','UNRESOLVED')} temporal_reason={e.get('temporal_reason','')}: {e['snippet']}" for i,e in enumerate(evidence)])
    prompt=f"QUESTION: {question}\n\nEVIDENCE:\n{context}\n\nReturn JSON only."
    if settings.llm_provider=="ollama":
        url=settings.llm_base_url.rstrip("/")+"/api/chat"
        try:
            r=httpx.post(url,json={"model":settings.llm_model,"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],"stream":False,"format":"json"},timeout=120)
            r.raise_for_status()
            data=r.json(); return json.loads(data["message"]["content"])
        except Exception as exc:
            logger.warning("Ollama answer generation failed; trying configured fallback: %s",exc)
    if settings.llm_provider in {"openai","openai-compatible"} and settings.llm_api_key:
        try:
            from openai import OpenAI
            client=OpenAI(api_key=settings.llm_api_key,base_url=settings.llm_base_url or None)
            r=client.chat.completions.create(model=settings.llm_model,messages=[{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],temperature=0,response_format={"type":"json_object"})
            return json.loads(r.choices[0].message.content)
        except Exception as exc:
            logger.warning("OpenAI-compatible answer generation failed: %s",exc)
    raise RuntimeError("LLM provider unavailable. Configure Ollama or an OpenAI-compatible provider before asking VeriRAG to generate an answer.")


def verify_claim_with_llm(claim,evidence):
    prompt_evidence=[{"snippet":item["snippet"]} for item in evidence]
    return _cached_call("claim-verification",{"claim":claim,"evidence":prompt_evidence},lambda:_verify_claim_with_llm_uncached(claim,evidence))


def _verify_claim_with_llm_uncached(claim, evidence):
    """Verify one claim against supplied evidence using the configured LLM."""
    context = "\n\n".join([f"[EVIDENCE {i+1}] {e['snippet']}" for i, e in enumerate(evidence)])
    system = """You are a strict evidence verifier. Compare the CLAIM only with the supplied EVIDENCE. Return JSON only with keys status, confidence, reason. status must be exactly SUPPORTED, PARTIALLY_SUPPORTED, CONTRADICTED, or UNVERIFIED. Do not use outside knowledge. A claim is CONTRADICTED only when the evidence explicitly conflicts with it. If evidence is insufficient, use UNVERIFIED."""
    prompt = f"CLAIM: {claim}\n\nEVIDENCE:\n{context}\n\nReturn JSON only."
    if settings.llm_provider == "ollama":
        import httpx, json
        r = httpx.post(settings.llm_base_url.rstrip("/") + "/api/chat", json={"model":settings.llm_model,"messages":[{"role":"system","content":system},{"role":"user","content":prompt}],"stream":False,"format":"json"}, timeout=120)
        r.raise_for_status()
        return json.loads(r.json()["message"]["content"])
    if settings.llm_provider in {"openai", "openai-compatible"} and settings.llm_api_key:
        from openai import OpenAI
        import json
        client=OpenAI(api_key=settings.llm_api_key,base_url=settings.llm_base_url or None)
        r=client.chat.completions.create(model=settings.llm_model,messages=[{"role":"system","content":system},{"role":"user","content":prompt}],temperature=0,response_format={"type":"json_object"})
        return json.loads(r.choices[0].message.content)
    raise RuntimeError("LLM provider unavailable for claim verification.")
