import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  Clock3,
  FileText,
  GitBranch,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { QueryAnalysisResponse } from "@shared/api";
import { apiFetch } from "@/lib/api";

const statusColor: Record<QueryAnalysisResponse["status"], string> = {
  ANSWERABLE: "#45ae91",
  PARTIALLY_ANSWERABLE: "#d09339",
  CONTRADICTED: "#c35f67",
  INSUFFICIENT_EVIDENCE: "#c35f67",
  OUT_OF_SCOPE: "#9c8df0",
  KNOWLEDGE_GAP: "#c18432",
};
const claimColor = (status: string) =>
  status === "SUPPORTED"
    ? "#45ae91"
    : status === "CONTRADICTED"
      ? "#c35f67"
      : "#d09339";

    type SavedQuery = { id: string; question: string; answer: string; status: QueryAnalysisResponse["status"]; createdAt: string };

export default function Ask() {
  const [query, setQuery] = useState(
    "What is the current remote-work allowance?",
  );
  const [result, setResult] = useState<QueryAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<SavedQuery[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const requestInProgress = useRef(false);
  useEffect(() => {
    apiFetch("/api/queries?limit=5")
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load saved queries");
        setHistory(await response.json());
      })
      .catch(() => setHistory([]))
      .finally(() => setHistoryLoading(false));
  }, []);

  const openSavedQuery = async (saved: SavedQuery) => {
    setQuery(saved.question);
    setLoading(true);
    setError("");
    try {
      const response = await apiFetch(`/api/query/${saved.id}`);
      if (!response.ok) throw new Error("Unable to load saved answer");
      setResult(await response.json());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load saved answer");
    } finally {
      setLoading(false);
    }
  };

  const runQuery = async () => {
    if (!query.trim() || requestInProgress.current) return;
    requestInProgress.current = true;
    setLoading(true);
    setError("");
    try {
      const response = await apiFetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query }),
      });
      if (!response.ok)
        throw new Error(
          (await response.json()).error || "Unable to analyze question",
        );
      const saved = await response.json() as QueryAnalysisResponse;
      setResult(saved);
      setHistory((current) => [{ id: saved.queryId, question: saved.question, answer: saved.answer, status: saved.status, createdAt: saved.generatedAt }, ...current.filter((item) => item.id !== saved.queryId)].slice(0, 5));
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to analyze question",
      );
      setResult(null);
    } finally {
      requestInProgress.current = false;
      setLoading(false);
    }
  };

  return (
    <div className="animate-in fade-in duration-500">
      <div className="mb-8">
        <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[.15em] text-[#8491a3]">
          <Sparkles className="h-3.5 w-3.5 text-[#c2d95e]" />
          Question intelligence
        </div>
        <h1 className="font-display text-3xl font-semibold tracking-[-.045em] text-[#172333] sm:text-[40px]">
          Ask VeriRAG<span className="text-[#d6e887]">.</span>
        </h1>
        <p className="mt-2 max-w-xl text-sm text-[#718096]">
          Analyze, retrieve, verify, and explain what your documents can
          actually support.
        </p>
      </div>
      <div className="mb-6 rounded-2xl bg-[#101827] p-3 shadow-[0_12px_32px_rgba(16,24,39,.15)] sm:p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="flex flex-1 items-center gap-3 rounded-xl bg-white/[.08] px-4 py-3">
            <Search className="h-4 w-4 shrink-0 text-[#d8f76c]" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && !loading && runQuery()}
              className="w-full bg-transparent text-sm text-white outline-none placeholder:text-white/35"
              placeholder="Ask anything about your knowledge base..."
            />
          </div>
          <button
            onClick={runQuery}
            disabled={loading}
            className="flex h-12 items-center justify-center gap-2 rounded-xl bg-[#d8f76c] px-5 text-xs font-bold text-[#172333] transition hover:bg-[#e4ff86] disabled:opacity-60"
          >
            {loading ? "Analyzing..." : "Analyze question"}{" "}
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 px-1 text-[10px] text-white/40">
          <span>Try:</span>
          <button
            onClick={() =>
              setQuery("What is the penalty for violating the WFH policy?")
            }
            className="rounded-md bg-white/[.07] px-2 py-1 hover:text-white/70"
          >
            policy violation penalty
          </button>
          <button
            onClick={() => setQuery("What is the maternity leave policy?")}
            className="rounded-md bg-white/[.07] px-2 py-1 hover:text-white/70"
          >
            maternity leave policy
          </button>
          <button
            onClick={() => setQuery("What was the WFH policy in 2022?")}
            className="rounded-md bg-white/[.07] px-2 py-1 hover:text-white/70"
          >
            2022 WFH policy
          </button>
        </div>
      </div>
      {error && (
        <div className="mb-5 rounded-xl border border-[#f2caca] bg-[#fff5f5] p-4 text-xs text-[#b25c63]">
          {error}
        </div>
      )}
      {(history.length > 0 || historyLoading) && (
        <section className="mb-6 rounded-2xl border border-[#e3e8f0] bg-white p-5">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock3 className="h-4 w-4 text-[#9aa6b5]" />
              <h2 className="font-display text-sm font-semibold text-[#344154]">Recent questions</h2>
            </div>
            <span className="text-[10px] text-[#9aa6b5]">Latest 5</span>
          </div>
          {historyLoading ? <p className="text-xs text-[#8b98a8]">Loading saved questions...</p> : (
            <div className="divide-y divide-[#edf0f4]">
              {history.map((saved) => (
                <button key={saved.id} onClick={() => openSavedQuery(saved)} disabled={loading} className="block w-full py-3 text-left transition hover:bg-[#fbfcfe] disabled:opacity-60">
                  <span className="block truncate text-xs font-semibold text-[#344154]">{saved.question}</span>
                  <span className="mt-1 block line-clamp-2 text-[11px] leading-4 text-[#718096]">{saved.answer}</span>
                  <span className="mt-1 block text-[9px] text-[#9aa6b5]">{saved.status} · {new Date(saved.createdAt).toLocaleString()}</span>
                </button>
              ))}
            </div>
          )}
        </section>
      )}
      {!result && !loading && (
        <div className="flex min-h-[380px] items-center justify-center rounded-2xl border border-[#e3e8f0] bg-white">
          <div className="max-w-sm px-6 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#eff8d0] text-[#718c27]">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <p className="mt-4 text-sm font-semibold text-[#344154]">
              Ask a question to begin analysis
            </p>
            <p className="mt-2 text-xs leading-5 text-[#8b98a8]">
              VeriRAG will separate supported information, missing information,
              conflicts, inference, trust, and knowledge gaps.
            </p>
          </div>
        </div>
      )}
      {loading && (
        <div className="flex min-h-[380px] items-center justify-center rounded-2xl border border-[#e3e8f0] bg-white">
          <div className="text-center">
            <Sparkles className="mx-auto h-6 w-6 animate-pulse text-[#9ab445]" />
            <p className="mt-4 text-sm font-semibold">
              Running question intelligence...
            </p>
            <p className="mt-1 text-xs text-[#8b98a8]">
              Analyzing intent, retrieving evidence, and calculating coverage
            </p>
          </div>
        </div>
      )}
      {result && (
        <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
          <div className="space-y-5">
            <section className="rounded-2xl border border-[#e3e8f0] bg-white p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[.16em] text-[#9aa6b5]">
                    Question analysis · {result.intent}
                  </p>
                  <h2 className="mt-2 font-display text-lg font-semibold">
                    {result.topic}
                  </h2>
                  <p className="mt-1 text-xs text-[#8491a3]">
                    Reformulated search:{" "}
                    {result.reformulations.join(" · ") || "none"}
                  </p>
                </div>
                <span
                  className="rounded-md px-2.5 py-1.5 text-[9px] font-bold tracking-wide"
                  style={{
                    color: statusColor[result.status],
                    backgroundColor: `${statusColor[result.status]}18`,
                  }}
                >
                  {result.status}
                </span>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl bg-[#f7f9fb] p-3">
                  <p className="text-[9px] font-bold uppercase tracking-wide text-[#9aa6b5]">
                    Coverage
                  </p>
                  <p className="mt-2 font-display text-2xl font-semibold">
                    {result.coverage}%
                  </p>
                </div>
                <div className="rounded-xl bg-[#f7f9fb] p-3">
                  <p className="text-[9px] font-bold uppercase tracking-wide text-[#9aa6b5]">
                    Evidence
                  </p>
                  <p className="mt-2 font-display text-2xl font-semibold">
                    {result.evidence.length}
                  </p>
                </div>
                <div className="rounded-xl bg-[#f7f9fb] p-3">
                  <p className="text-[9px] font-bold uppercase tracking-wide text-[#9aa6b5]">
                    Keywords
                  </p>
                  <p className="mt-2 truncate text-xs font-semibold">
                    {result.keywords.join(", ") || "none"}
                  </p>
                </div>
              </div>
            </section>
            <section className="rounded-2xl border border-[#e3e8f0] bg-white p-6">
              <div className="flex items-center gap-2">
                <Check className="h-4 w-4 text-[#45ae91]" />
                <h2 className="font-display text-lg font-semibold">
                  Supported information
                </h2>
              </div>
              <p className="mt-5 text-[20px] font-medium leading-8 tracking-[-.025em] text-[#273447]">
                {result.answer}
              </p>
              {result.missingInformation.length > 0 && (
                <div className="mt-5 rounded-xl border border-[#f1dfbd] bg-[#fffaf0] p-4">
                  <p className="text-[10px] font-bold uppercase tracking-[.14em] text-[#b27d35]">
                    Missing information
                  </p>
                  <ul className="mt-2 space-y-1 text-xs leading-5 text-[#8d734c]">
                    {result.missingInformation.map((item) => (
                      <li key={`${item}-${result.missingInformation.indexOf(item)}`}>• {item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
            <section className="rounded-2xl border border-[#e3e8f0] bg-white p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-[#9c8df0]" />
                  <h2 className="font-display text-lg font-semibold">
                    Claim verification
                  </h2>
                </div>
                <span className="text-[10px] text-[#9aa6b5]">
                  {result.claims.length} claims from retrieved evidence
                </span>
              </div>
              <div className="mt-5 space-y-3">
                {result.claims.length ? (
                  result.claims.map((claim, index) => (
                      <div
                        className="rounded-xl border border-[#edf0f4] p-4"
                        key={`${claim.text}-${index}`}
                    >
                      <div className="flex items-start gap-3">
                        <span
                          className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full"
                          style={{
                            color: claimColor(claim.status),
                            backgroundColor: `${claimColor(claim.status)}18`,
                          }}
                        >
                          {claim.status === "SUPPORTED" ? (
                            <Check className="h-3 w-3" />
                          ) : (
                            <span className="text-[11px] font-bold">!</span>
                          )}
                        </span>
                        <div>
                          <p className="text-xs font-semibold leading-5 text-[#354256]">
                            {claim.text}
                          </p>
                          <span
                            className="mt-2 inline-flex rounded-md px-2 py-1 text-[9px] font-bold"
                            style={{
                              color: claimColor(claim.status),
                              backgroundColor: `${claimColor(claim.status)}18`,
                            }}
                          >
                            {claim.status}
                          </span>
                          <span className="ml-2 text-[10px] text-[#92a0af]">Confidence: {Math.round(claim.confidence)}%</span>
                          <p className="mt-2 text-[10px] text-[#92a0af]">
                            Evidence: {claim.evidence.length ? claim.evidence.map((item) => `${item.document} · p.${item.page} · ${item.version} · ${item.temporalStatus}`).join(" | ") : "none"}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-[#8b98a8]">
                    No claims could be generated because no relevant evidence
                    was retrieved.
                  </p>
                )}
              </div>
            </section>
            <section className="rounded-2xl border border-[#e3e8f0] bg-white p-6">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-[#7187dc]" />
                <h2 className="font-display text-lg font-semibold">Evidence</h2>
              </div>
              <div className="mt-4 space-y-3">
                {result.evidence.length ? (
                  result.evidence.map((item, index) => (
                      <div
                        className="rounded-xl bg-[#f7f9fb] p-4"
                        key={`${item.documentId}-${item.document}-${index}`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-xs font-semibold text-[#344154]">
                          {item.document}
                        </p>
                        <span className="text-[10px] font-bold text-[#45ae91]">
                          {item.relevance}% relevant
                        </span>
                      </div>
                      <p className="mt-1 text-[10px] text-[#8996a7]">
                        {item.version} · {item.source}
                      </p>
                      <p className="mt-3 text-xs leading-5 text-[#647286]">
                        {item.snippet}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-[#8b98a8]">
                    No evidence was found in the persisted document store.
                  </p>
                )}
              </div>
            </section>
          </div>
          <aside className="space-y-5">
            <section className="rounded-2xl bg-[#101827] p-6 text-white">
              <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-white/45">
                Interpretable trust
              </p>
              <p className="mt-2 font-display text-4xl font-semibold tracking-[-.06em]">
                {result.trust.score}
                <span className="text-lg text-white/35">/100</span>
              </p>
              <p className="mt-2 text-xs font-semibold text-[#d8f76c]">
                {result.trust.score >= 90
                  ? "Very high"
                  : result.trust.score >= 75
                    ? "High"
                    : result.trust.score >= 50
                      ? "Medium"
                      : "Low"}{" "}
                trust
              </p>
              <div className="mt-6 space-y-3">
                {[
                  ["Evidence strength", result.trust.evidenceStrength],
                  ["Source authority", result.trust.sourceAuthority],
                  ["Recency", result.trust.recency],
                  ["Agreement", result.trust.agreement],
                  ["Contradiction penalty", result.trust.contradictionPenalty],
                  ["Unverified penalty", result.trust.unverifiedPenalty],
                ].map(([label, value]) => (
                  <div key={label as string}>
                    <div className="mb-1 flex justify-between text-[10px] text-white/55">
                      <span>{label}</span>
                      <span>{value}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-[#d8f76c]"
                        style={{ width: `${Math.min(100, Number(value))}%`, backgroundColor: String(label).includes("penalty") ? "#c35f67" : "#d8f76c" }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-5 border-t border-white/10 pt-4 text-[10px] leading-4 text-white/45">
                {result.trust.explanation}
              </p>
            </section>
            <section className="rounded-2xl border border-[#e3e8f0] bg-white p-6">
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-[#9c8df0]" />
                <h2 className="font-display text-sm font-semibold">
                  Knowledge gap analysis
                </h2>
              </div>
              <p className="mt-4 text-xs leading-5 text-[#657487]">
                {result.knowledgeGap.detected
                  ? result.knowledgeGap.reason
                  : "No knowledge gap detected for this query."}
              </p>
              {result.knowledgeGap.detected && (
                <span className="mt-4 inline-flex rounded-md bg-[#fff5e8] px-2 py-1 text-[9px] font-bold text-[#b27d35]">
                  KNOWLEDGE GAP · {result.knowledgeGap.topic}
                </span>
              )}
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}
