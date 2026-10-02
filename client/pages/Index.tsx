import { useEffect, useState } from "react";
import { ArrowUpRight, BarChart3, FileText, GitBranch, ShieldCheck, Tags, UploadCloud } from "lucide-react";
import { Link } from "react-router-dom";
import { apiFetch } from "@/lib/api";

export default function Index() {
  const [data, setData] = useState<any>(null);
  const [docs, setDocs] = useState<any[]>([]);
  const [error, setError] = useState("");
  const load = async () => {
    try {
      setError("");
      const [a, d] = await Promise.all([apiFetch("/api/analytics"), apiFetch("/api/documents")]);
      if (!a.ok || !d.ok) throw new Error("Dashboard data unavailable");
      setData(await a.json()); setDocs(await d.json());
    } catch (e) { setError(e instanceof Error ? e.message : "Dashboard data unavailable"); }
  };
  useEffect(() => { load(); }, []);
  const stats = [
    ["Indexed documents", data?.documents ?? 0, FileText],
    ["Evidence claims", data?.claims ?? 0, ShieldCheck],
    ["Average trust", data?.averageTrust ?? 0, BarChart3],
    ["Knowledge gaps", data?.knowledgeGaps ?? 0, Tags],
  ];
  return <div className="space-y-7 animate-in fade-in duration-500">
    <section className="flex flex-col justify-between gap-5 md:flex-row md:items-end"><div><p className="mb-3 text-[11px] font-semibold uppercase tracking-[.15em] text-[#8491a3]">Workspace overview</p><h1 className="font-display text-3xl font-semibold tracking-[-.045em] sm:text-[40px]">VeriRAG overview<span className="text-[#d6e887]">.</span></h1><p className="mt-2 text-sm text-[#718096]">Live metrics from your persisted documents, queries, claims and knowledge gaps.</p></div><Link to="/ask" className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#101827] px-5 text-xs font-semibold text-white"><span>Ask your knowledge base</span><ArrowUpRight className="h-4 w-4 text-[#d8f76c]" /></Link></section>
    {error && <div className="rounded-xl bg-[#fff5f5] p-4 text-xs text-[#b25c63]">{error}<button onClick={load} className="ml-3 font-bold underline">Retry</button></div>}
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{stats.map(([label,value,Icon]:any) => <div key={label} className="rounded-2xl border border-[#e3e8f0] bg-white p-5"><div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#f1f5df] text-[#718c27]"><Icon className="h-4 w-4" /></div><p className="mt-5 font-display text-3xl font-semibold">{value}</p><p className="mt-1 text-[11px] text-[#8190a3]">{label}</p></div>)}</section>
    <section className="grid gap-5 xl:grid-cols-2">
      <div className="rounded-2xl border border-[#e3e8f0] bg-white p-6"><div className="flex items-center gap-2"><GitBranch className="h-4 w-4 text-[#9c8df0]"/><h2 className="font-display text-lg font-semibold">Evidence system</h2></div><div className="mt-6 grid grid-cols-2 gap-3 text-xs"><div className="rounded-xl bg-[#f7f9fb] p-4"><p className="text-[#9aa6b5]">Queries</p><p className="mt-1 text-2xl font-semibold">{data?.queries ?? 0}</p></div><div className="rounded-xl bg-[#f7f9fb] p-4"><p className="text-[#9aa6b5]">Evidence records</p><p className="mt-1 text-2xl font-semibold">{data?.evidence ?? 0}</p></div><div className="rounded-xl bg-[#f7f9fb] p-4"><p className="text-[#9aa6b5]">Temporal relations</p><p className="mt-1 text-2xl font-semibold">{data?.temporalRelations ?? 0}</p></div><div className="rounded-xl bg-[#f7f9fb] p-4"><p className="text-[#9aa6b5]">Avg. evidence coverage</p><p className="mt-1 text-2xl font-semibold">{data?.queries ? Math.round((data.queryTimeline || []).reduce((s:any,x:any)=>s+x.coverage,0)/data.queries) : 0}%</p></div></div></div>
      <div className="rounded-2xl border border-[#e3e8f0] bg-white p-6"><div className="flex items-center justify-between"><div><h2 className="font-display text-lg font-semibold">Recent documents</h2><p className="mt-1 text-xs text-[#8491a3]">Persisted files currently available to retrieval.</p></div><Link to="/documents" className="text-[11px] font-semibold text-[#657487]">View all</Link></div><div className="mt-5 space-y-3">{docs.slice(0,5).map((d:any)=><div key={d.id} className="flex items-center gap-3 rounded-xl bg-[#f7f9fb] p-3"><FileText className="h-4 w-4 text-[#7187dc]"/><div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold">{d.filename}</p><p className="text-[10px] text-[#8b98a8]">{d.version} · {d.chunks} chunks · {d.status}</p></div></div>)}{docs.length===0&&<p className="py-8 text-center text-xs text-[#8b98a8]">No documents yet.</p>}</div></div>
    </section>
    <section className="rounded-2xl border border-dashed border-[#cfd8e4] bg-[#fbfcfe] p-5"><div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center"><div><h3 className="text-sm font-semibold">Bring more knowledge into VeriRAG</h3><p className="mt-1 text-xs text-[#8491a3]">Upload policies, manuals, reports or scanned documents for evidence-grounded analysis.</p></div><Link to="/documents" className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#dbe3eb] bg-white px-3.5 text-[11px] font-semibold"><UploadCloud className="h-3.5 w-3.5"/>Upload documents</Link></div></section>
  </div>;
}
