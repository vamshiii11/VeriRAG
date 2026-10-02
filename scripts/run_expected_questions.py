import json
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000"
EMAIL = "workflow-test-20260923@example.com"
PASSWORD = "VeriRAGtest123!"
QUESTIONS = [
    {
        "question": "What is the current annual paid leave allowance for full-time employees, and how does it compare to the 2025 policy?",
        "expected": "Current (2026) allowance is 24 days. In 2025 (v1.0), it was 18 days.",
        "sources": {"employee_policy_v2.pdf", "employee_policy_v1.pdf"},
    },
    {
        "question": "How many days per month can an employee work from home under the latest company policy?",
        "expected": "4 days per month under Policy v2.0, superseding the 2025 limit of 2 days per month.",
        "sources": {"employee_policy_v2.pdf", "employee_handbook_2026.docx"},
    },
]


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=600) as client:
        login = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        results = []
        for item in QUESTIONS:
            response = client.post("/api/query", headers=headers, json={"question": item["question"]})
            response.raise_for_status()
            payload = response.json()
            citations = {e["document"] for e in payload.get("evidence", [])}
            results.append(
                {
                    "question": item["question"],
                    "expected": item["expected"],
                    "answer": payload.get("answer"),
                    "status": payload.get("status"),
                    "trust": payload.get("trust", {}).get("score"),
                    "citations_found": sorted(citations),
                    "expected_sources_found": sorted(citations & item["sources"]),
                    "claims": payload.get("claims", []),
                }
            )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
