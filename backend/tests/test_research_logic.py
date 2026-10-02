from datetime import datetime
from types import SimpleNamespace

from app.query_engine import calculate_trust, resolve_temporal_evidence, verify_claim


def document(title, version, effective, authority=50, expiry=None):
    return SimpleNamespace(
        id=f"{title}-{version}",
        title=title,
        version=version,
        effective_date=effective,
        expiry_date=expiry,
        authority=authority,
        filename=f"{title}-{version}.txt",
    )


def evidence(doc, snippet, rerank=0.9):
    return {"document": doc, "snippet": snippet, "rerank": rerank}


def test_current_query_prefers_newer_policy():
    old = evidence(document("Leave Policy", "1.0", "2024-01-01"), "Employees receive 20 leave days.")
    new = evidence(document("Leave Policy", "2.0", "2026-01-01"), "Employees receive 25 leave days.")
    resolved = resolve_temporal_evidence("What is the current leave policy?", [old, new], [])
    assert next(item for item in resolved if item["document"].version == "2.0")["temporal_status"] == "CURRENT"
    assert next(item for item in resolved if item["document"].version == "1.0")["temporal_status"] == "SUPERSEDED"


def test_historical_query_selects_historically_valid_policy():
    old = evidence(document("Leave Policy", "1.0", "2024-01-01"), "Employees receive 20 leave days.")
    new = evidence(document("Leave Policy", "2.0", "2026-01-01"), "Employees receive 25 leave days.")
    resolved = resolve_temporal_evidence("What was the leave policy in 2024?", [old, new], [])
    assert next(item for item in resolved if item["document"].version == "1.0")["temporal_status"] == "CURRENT"
    assert next(item for item in resolved if item["document"].version == "2.0")["temporal_status"] == "HISTORICAL"


def test_expired_policy_is_not_current():
    expired = evidence(document("Leave Policy", "1.0", "2020-01-01", expiry="2022-12-31"), "Employees receive 20 leave days.")
    resolved = resolve_temporal_evidence("What is the current leave policy?", [expired], [])
    assert resolved[0]["temporal_status"] == "EXPIRED"


def test_equal_date_equal_authority_is_conflicted():
    first = evidence(document("Leave Policy", "A", "2026-01-01", authority=70), "Employees receive 20 leave days.")
    second = evidence(document("Leave Policy", "B", "2026-01-01", authority=70), "Employees receive 25 leave days.")
    resolved = resolve_temporal_evidence("What is the current leave policy?", [first, second], [])
    assert {item["temporal_status"] for item in resolved} == {"CONFLICTED"}


def test_claim_verification_fallback_classifies_supported_and_contradicted():
    supported = verify_claim(None, "Employees can work remotely", [{"snippet": "Employees can work remotely two days per week."}])
    contradicted = verify_claim(None, "Employees can work remotely", [{"snippet": "Remote work is not allowed without approval."}])
    assert supported[0] in {"SUPPORTED", "PARTIALLY_SUPPORTED"}
    assert contradicted[0] == "CONTRADICTED"


def test_trust_penalizes_contradiction_and_conflict():
    evidence_row = SimpleNamespace(id="e1", rerank_score=.9, snippet="Two current policies disagree.", temporal_status="CONFLICTED", document=SimpleNamespace(authority=80, effective_date="2026-01-01"))
    claim = SimpleNamespace(status="CONTRADICTED", links=[SimpleNamespace(evidence_id="e1")])
    score, details = calculate_trust([claim], [evidence_row], "What is the current policy?")
    assert score < 80
    assert details["contradictionPenalty"] > 0
    assert details["agreement"] == 100
