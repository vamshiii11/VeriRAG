import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  ChevronDown,
  CircleHelp,
  FileSearch,
  GitBranch,
  LayoutDashboard,
  PanelLeft,
  Menu, X,
  Search,
  ShieldCheck,
  Sparkles,
  Tags,
  Upload,
} from "lucide-react";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

const navigation = [
  { label: "Overview", to: "/", icon: LayoutDashboard },
  { label: "Ask VeriRAG", to: "/ask", icon: Sparkles },
  { label: "Documents", to: "/documents", icon: FileSearch },
  { label: "Evidence graph", to: "/evidence", icon: GitBranch },
  { label: "Knowledge gaps", to: "/gaps", icon: Tags },
];

type WorkspaceLayoutProps = { onLogout: () => void };

export default function WorkspaceLayout({ onLogout }: WorkspaceLayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [globalSearch, setGlobalSearch] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [liveEvent, setLiveEvent] = useState("");
  const navigate = useNavigate();
  useEffect(() => {
    const t=localStorage.getItem("verirag-token"); if(!t) return;
    const protocol=window.location.protocol==="https:"?"wss":"ws";
    const ws=new WebSocket(`${protocol}://${window.location.host}/api/events?token=${encodeURIComponent(t)}`);
    ws.onmessage=(e)=>{try{const data=JSON.parse(e.data);setLiveEvent(data.message||data.stage||"Processing update");}catch{}};
    ws.onerror=()=>setLiveEvent("");
    return ()=>ws.close();
  }, []);
  useEffect(() => {
    const term=globalSearch.trim();
    if(term.length<2){setSearchResults([]);return;}
    const controller=new AbortController();
    const timeout=window.setTimeout(async()=>{
      try{
        const response=await apiFetch(`/api/search?q=${encodeURIComponent(term)}`,{signal:controller.signal});
        if(!response.ok) throw new Error("Search unavailable");
        setSearchResults(await response.json());
      }catch{
        if(!controller.signal.aborted) setSearchResults([]);
      }
    },250);
    return ()=>{window.clearTimeout(timeout);controller.abort();};
  },[globalSearch]);

  return (
    <div className="min-h-screen bg-[#f5f7fb] text-[#182230]">
      <aside className={cn("fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-[#e3e8f0] bg-[#101827] text-white transition-all duration-300 lg:flex", collapsed ? "w-[84px]" : "w-[252px]")}>
        <div className="flex h-[92px] items-center border-b border-white/10 px-6">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-[13px] bg-[#d8f76c] text-[#101827] shadow-[0_0_24px_rgba(216,247,108,.18)]">
              <ShieldCheck className="h-5 w-5" strokeWidth={2.4} />
              <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-[#101827] bg-[#65d8b1]" />
            </div>
            {!collapsed && <div className="whitespace-nowrap"><p className="font-display text-[17px] font-semibold tracking-[-0.02em]">Veri<span className="text-[#d8f76c]">RAG</span></p><p className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.16em] text-white/40">Evidence intelligence</p></div>}
          </div>
        </div>
        <div className="flex flex-1 flex-col px-3 py-7">
          {!collapsed && <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/35">Workspace</p>}
          <nav className="space-y-1.5">
            {navigation.map(({ label, to, icon: Icon }) => <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => cn("group flex h-11 items-center gap-3 rounded-xl px-3 text-[13px] font-medium transition-all", isActive ? "bg-white/10 text-[#d8f76c] shadow-inner" : "text-white/55 hover:bg-white/[.06] hover:text-white", collapsed && "justify-center px-0")}><Icon className={cn("h-[17px] w-[17px] shrink-0", "group-hover:text-[#d8f76c]")} strokeWidth={1.8} />{!collapsed && <span>{label}</span>}{!collapsed && label === "Ask VeriRAG" && <span className="ml-auto rounded-md bg-[#d8f76c] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-[#101827]">New</span>}</NavLink>)}
          </nav>
          {!collapsed && <><div className="my-7 border-t border-white/10" /><p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/35">System</p><div className="space-y-1.5"><NavLink to="/analytics" className="flex h-11 w-full items-center gap-3 rounded-xl px-3 text-left text-[13px] font-medium text-white/55 transition hover:bg-white/[.06] hover:text-white"><BarChart3 className="h-[17px] w-[17px]" strokeWidth={1.8} />Evaluation lab</NavLink><NavLink to="/help" className="flex h-11 w-full items-center gap-3 rounded-xl px-3 text-left text-[13px] font-medium text-white/55 transition hover:bg-white/[.06] hover:text-white"><BookOpen className="h-[17px] w-[17px]" strokeWidth={1.8} />Documentation</NavLink></div></>}
          <div onClick={onLogout} className="mt-auto cursor-pointer rounded-2xl border border-white/10 bg-white/[.04] p-3.5 transition hover:bg-white/[.08]" title="Sign out"><div className="flex items-center gap-2.5"><div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#b4a4ff] text-[10px] font-bold text-[#221f3d]">DV</div>{!collapsed && <div className="min-w-0"><p className="truncate text-xs font-semibold text-white/90">Darling Vamshi</p><p className="truncate text-[10px] text-white/40">Research workspace</p></div>}{!collapsed && <ChevronDown className="ml-auto h-3.5 w-3.5 text-white/40" />}</div></div>
        </div>
        <button onClick={() => setCollapsed(!collapsed)} className="m-3 flex h-10 items-center justify-center rounded-xl border border-white/10 text-white/45 transition hover:bg-white/[.06] hover:text-white" aria-label="Toggle sidebar"><PanelLeft className="h-4 w-4" /></button>
      </aside>
      {mobileOpen && <div className="fixed inset-0 z-40 bg-[#101827]/40 lg:hidden" onClick={()=>setMobileOpen(false)}>
        <aside className="h-full w-[280px] bg-[#101827] p-5 text-white" onClick={e=>e.stopPropagation()}>
          <div className="mb-6 flex items-center justify-between"><span className="font-display text-lg font-semibold">Veri<span className="text-[#d8f76c]">RAG</span></span><button onClick={()=>setMobileOpen(false)} aria-label="Close menu"><X className="h-5 w-5"/></button></div>
          <nav className="space-y-1.5">{navigation.map(({label,to,icon:Icon})=><NavLink key={to} to={to} end={to==="/"} onClick={()=>setMobileOpen(false)} className="flex h-11 items-center gap-3 rounded-xl px-3 text-sm text-white/65 hover:bg-white/10"><Icon className="h-4 w-4"/>{label}</NavLink>)}
          <NavLink to="/analytics" onClick={()=>setMobileOpen(false)} className="flex h-11 items-center gap-3 rounded-xl px-3 text-sm text-white/65 hover:bg-white/10"><BarChart3 className="h-4 w-4"/>Analytics</NavLink></nav>
        </aside>
      </div>}
      <main className={cn("min-h-screen transition-all duration-300", collapsed ? "lg:pl-[84px]" : "lg:pl-[252px]")}>
        <header className="sticky top-0 z-20 flex h-[76px] items-center justify-between border-b border-[#e3e8f0]/80 bg-[#f5f7fb]/90 px-5 backdrop-blur-xl sm:px-8 lg:px-10"><div className="flex items-center gap-2 lg:hidden"><button onClick={()=>setMobileOpen(true)} className="flex h-9 w-9 items-center justify-center rounded-xl border border-[#e3e8f0] bg-white" aria-label="Open menu"><Menu className="h-4 w-4"/></button><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#101827] text-[#d8f76c]"><ShieldCheck className="h-4 w-4" /></div><span className="font-display font-semibold">VeriRAG</span></div><div className="relative hidden w-[310px] sm:block"><Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9aa6b7]" /><input value={globalSearch} onChange={e=>setGlobalSearch(e.target.value)} className="h-10 w-full rounded-xl border border-[#e3e8f0] bg-white pl-10 pr-4 text-xs outline-none transition placeholder:text-[#9aa6b7] focus:border-[#a7b986] focus:ring-4 focus:ring-[#d8f76c]/20" placeholder="Search documents, claims, queries..." />
          {globalSearch.trim().length>1 && <div className="absolute left-0 right-0 top-12 z-50 max-h-72 overflow-auto rounded-xl border border-[#e3e8f0] bg-white p-2 shadow-xl">{searchResults.length?searchResults.map((r:any)=><button key={`${r.type}-${r.id}`} onClick={()=>{setGlobalSearch("");setSearchResults([]);navigate(r.type==="document"?"/documents":r.type==="claim"?"/ask":`/ask?queryId=${r.id}`)}} className="w-full rounded-lg p-2.5 text-left hover:bg-[#f5f7fb]"><p className="text-[10px] font-bold uppercase text-[#9aa6b5]">{r.type}</p><p className="mt-1 text-xs font-semibold text-[#344154]">{r.title}</p><p className="text-[10px] text-[#8b98a8]">{r.text}</p></button>):<p className="p-3 text-xs text-[#8b98a8]">No results.</p>}</div>}
        </div><div className="flex items-center gap-3"><div className="hidden items-center gap-2 rounded-full border border-[#dbe3eb] bg-white px-3 py-2 text-[11px] font-semibold text-[#657286] sm:flex"><span className={`h-2 w-2 rounded-full ${liveEvent?"bg-[#d09339] animate-pulse":"bg-[#65d8b1]"}`} />{liveEvent||"All systems operational"}</div><button onClick={() => navigate("/help")} className="flex h-9 w-9 items-center justify-center rounded-xl border border-[#e3e8f0] bg-white text-[#657286] transition hover:border-[#c6d39b] hover:text-[#182230]" aria-label="Open documentation"><CircleHelp className="h-4 w-4" /></button><button onClick={() => navigate("/documents")} className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#101827] text-[#d8f76c] transition hover:bg-[#1b2a3f]" aria-label="Upload documents"><Upload className="h-4 w-4" /></button></div></header>
        <div className="mx-auto max-w-[1480px] px-5 py-8 sm:px-8 lg:px-10"><Outlet /></div>
      </main>
    </div>
  );
}
