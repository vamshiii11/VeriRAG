import "./global.css";
import { Toaster } from "@/components/ui/toaster";
import { createRoot } from "react-dom/client";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useEffect, useState } from "react";
import Index from "./pages/Index";
import Login from "./pages/Login";
import Ask from "./pages/Ask";
import Documents from "./pages/Documents";
import Evidence from "./pages/Evidence";
import Gaps from "./pages/Gaps";
import Analytics from "./pages/Analytics";
import Help from "./pages/Help";
import NotFound from "./pages/NotFound";
import WorkspaceLayout from "./components/WorkspaceLayout";
import { API_TOKEN_KEY } from "./lib/api";

const queryClient = new QueryClient();

const App = () => {
  const [authenticated, setAuthenticated] = useState(() => Boolean(localStorage.getItem(API_TOKEN_KEY)));
  useEffect(() => {
    const handleUnauthorized = () => {
      localStorage.removeItem("verirag-user-email");
      queryClient.clear();
      setAuthenticated(false);
    };
    window.addEventListener("verirag:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("verirag:unauthorized", handleUnauthorized);
  }, []);
  const login = (token: string, email: string) => { localStorage.setItem(API_TOKEN_KEY, token); localStorage.setItem("verirag-user-email", email); setAuthenticated(true); };
  const logout = () => { localStorage.removeItem(API_TOKEN_KEY); localStorage.removeItem("verirag-user-email"); setAuthenticated(false); };
  return <QueryClientProvider client={queryClient}><TooltipProvider><Toaster /><Sonner /><BrowserRouter>
    <Routes>
      <Route path="/login" element={authenticated ? <Navigate to="/" replace /> : <Login onLogin={login} />} />
      <Route element={authenticated ? <WorkspaceLayout onLogout={logout} /> : <Navigate to="/login" replace />}>
        <Route path="/" element={<Index />} /><Route path="/ask" element={<Ask />} /><Route path="/documents" element={<Documents />} />
        <Route path="/evidence" element={<Evidence />} /><Route path="/gaps" element={<Gaps />} /><Route path="/analytics" element={<Analytics />} /><Route path="/help" element={<Help />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  </BrowserRouter></TooltipProvider></QueryClientProvider>;
};

createRoot(document.getElementById("root")!).render(<App />);
