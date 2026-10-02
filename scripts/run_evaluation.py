"""Run measured Basic RAG versus VeriRAG cases against a running API.

The script never fabricates scores. It records raw answers and source hits, and
only computes checks that have explicit expectations in the case file.
"""
import argparse
import json
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--cases", default="data/evaluation_cases.json")
    parser.add_argument("--output", default="evaluation-results.json")
    args = parser.parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    with httpx.Client(base_url=args.base_url, timeout=600) as client:
        login = client.post("/api/auth/login", json={"email": args.email, "password": args.password})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        results = []
        for case in cases:
            baseline = client.post("/api/baseline-query", headers=headers, json={"question": case["question"]})
            verirag = client.post("/api/query", headers=headers, json={"question": case["question"]})
            baseline.raise_for_status(); verirag.raise_for_status()
            basic_payload = baseline.json(); veri_payload = verirag.json()
            basic_sources = {item["document"] for item in basic_payload.get("evidence", [])}
            veri_sources = {item["document"] for item in veri_payload.get("evidence", [])}
            expected_sources = set(case.get("expected_sources", []))
            expected_terms = [term.lower() for term in case.get("expected_answer_contains", [])]
            results.append({
                "id": case["id"],
                "question": case["question"],
                "baseline": {"answer": basic_payload.get("answer"), "sources": sorted(basic_sources), "source_hits": sorted(basic_sources & expected_sources)},
                "verirag": {"answer": veri_payload.get("answer"), "status": veri_payload.get("status"), "trust": veri_payload.get("trust"), "sources": sorted(veri_sources), "source_hits": sorted(veri_sources & expected_sources), "knowledge_gap": veri_payload.get("knowledgeGap")},
                "checks": {
                    "verirag_expected_sources_found": sorted(veri_sources & expected_sources) == sorted(expected_sources) if expected_sources else True,
                    "verirag_expected_terms_found": all(term in str(veri_payload.get("answer", "")).lower() for term in expected_terms) if expected_terms else None,
                },
            })
    Path(args.output).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
