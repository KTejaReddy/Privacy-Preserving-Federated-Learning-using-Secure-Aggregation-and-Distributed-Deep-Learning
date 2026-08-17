import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Activity,
  Bell,
  Bot,
  Boxes,
  BrainCircuit,
  Building2,
  Database,
  FlaskConical,
  Gauge,
  GitBranch,
  GraduationCap,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  Network,
  PieChart,
  Rocket,
  ScrollText,
  Settings,
  Shield,
  ShieldCheck,
  Sparkles,
  Train,
  Users,
  X,
  Zap,
} from "lucide-react";
import clsx from "clsx";
import { useAuth } from "./auth";
import { Badge } from "./ui";

interface NavItem {
  label: string;
  to: string;
  icon: React.ReactNode;
  perm?: string;
  section: string;
}

const NAV: NavItem[] = [
  { section: "Workspace", label: "Executive Dashboard", to: "/", icon: <LayoutDashboard size={16} />, perm: "analytics:view" },
  { section: "Workspace", label: "Trainer Mode", to: "/trainer", icon: <GraduationCap size={16} />, perm: "training:view" },
  { section: "Federated Network", label: "Organizations", to: "/organizations", icon: <Building2 size={16} />, perm: "orgs:view" },
  { section: "Federated Network", label: "Federated Nodes", to: "/nodes", icon: <Network size={16} />, perm: "nodes:view" },
  { section: "Federated Network", label: "Dataset Registry", to: "/datasets", icon: <Database size={16} />, perm: "datasets:view" },
  { section: "Federated Network", label: "Communication Monitor", to: "/monitor", icon: <Activity size={16} />, perm: "monitor:view" },
  { section: "Training", label: "Training Center", to: "/training", icon: <Train size={16} />, perm: "training:view" },
  { section: "Training", label: "Federated Coordinator", to: "/coordinator", icon: <ListChecks size={16} />, perm: "training:view" },
  { section: "Training", label: "Secure Aggregation", to: "/aggregation", icon: <Shield size={16} />, perm: "training:view" },
  { section: "Models", label: "Global Model Registry", to: "/models", icon: <Boxes size={16} />, perm: "models:view" },
  { section: "Models", label: "Model Evaluation", to: "/evaluation", icon: <Gauge size={16} />, perm: "evaluation:view" },
  { section: "Models", label: "Explainable AI", to: "/explainability", icon: <BrainCircuit size={16} />, perm: "xai:view" },
  { section: "Insights", label: "Analytics", to: "/analytics", icon: <PieChart size={16} />, perm: "analytics:view" },
  { section: "Insights", label: "Reports", to: "/reports", icon: <ScrollText size={16} />, perm: "reports:view" },
  { section: "Insights", label: "Audit Center", to: "/audit", icon: <ShieldCheck size={16} />, perm: "audit:view" },
  { section: "Intelligence", label: "AI Assistant", to: "/assistant", icon: <Bot size={16} />, perm: "ai:use" },
  { section: "Intelligence", label: "AI Integrations", to: "/ai", icon: <Sparkles size={16} />, perm: "ai:use" },
  { section: "Experiments", label: "Federated Lab", to: "/lab", icon: <FlaskConical size={16} />, perm: "lab:view" },
  { section: "Platform", label: "Admin Panel", to: "/admin", icon: <Users size={16} />, perm: "admin:view" },
  { section: "Platform", label: "Settings", to: "/settings", icon: <Settings size={16} /> },
];

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-4 py-4">
      <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-brand-violet shadow-glow">
        <Zap size={18} className="text-ink-950" />
        <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 animate-ping rounded-full bg-mint/70" />
      </div>
      <div className="leading-tight">
        <p className="text-sm font-bold tracking-tight text-white">Federated AI</p>
        <p className="text-[10px] font-medium uppercase tracking-widest text-brand/70">Platform v1.0</p>
      </div>
    </div>
  );
}

export function Shell() {
  const { user, roleLabel, logout, can, permissions } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    const iv = setInterval(() => setOnline(navigator.onLine), 5000);
    return () => clearInterval(iv);
  }, []);

  const items = NAV.filter((n) => !n.perm || permissions.includes(n.perm));
  const sections = Array.from(new Set(items.map((i) => i.section)));

  const sidebar = (
    <div className="flex h-full flex-col">
      <Brand />
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 pb-4">
        {sections.map((section) => (
          <div key={section}>
            <p className="px-2 pb-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-600">
              {collapsed ? "·" : section}
            </p>
            <div className="space-y-0.5">
              {items
                .filter((i) => i.section === section)
                .map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    onClick={() => setMobileOpen(false)}
                    title={collapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      clsx(
                        "group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-all",
                        isActive
                          ? "bg-gradient-to-r from-brand/15 to-brand-violet/10 text-brand shadow-glow"
                          : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
                      )
                    }
                  >
                    <span className="shrink-0">{item.icon}</span>
                    {!collapsed && <span className="truncate">{item.label}</span>}
                  </NavLink>
                ))}
            </div>
          </div>
        ))}
      </nav>
      <div className="border-t border-white/5 p-3">
        <div className={clsx("flex items-center gap-2.5 rounded-lg px-2 py-2", !collapsed && "bg-white/5")}>
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand to-brand-violet text-xs font-bold text-ink-950">
            {user?.full_name?.slice(0, 2).toUpperCase()}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1 leading-tight">
              <p className="truncate text-xs font-semibold text-slate-200">{user?.full_name}</p>
              <p className="truncate text-[10px] text-brand/80">{roleLabel}</p>
            </div>
          )}
          {!collapsed && (
            <button
              onClick={() => {
                logout();
                navigate("/login");
              }}
              className="rounded p-1 text-slate-500 hover:bg-white/10 hover:text-danger"
              title="Sign out"
            >
              <LogOut size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden">
      {/* desktop sidebar */}
      <aside
        className={clsx(
          "hidden shrink-0 border-r border-white/5 bg-ink-900/70 backdrop-blur transition-all md:block",
          collapsed ? "w-16" : "w-60"
        )}
      >
        {sidebar}
      </aside>

      {/* mobile sidebar */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/70" onClick={() => setMobileOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-64 border-r border-white/10 bg-ink-900">
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-white/5 bg-ink-900/50 px-4 backdrop-blur">
          <div className="flex items-center gap-3">
            <button className="rounded-lg p-2 text-slate-400 hover:bg-white/5 md:hidden" onClick={() => setMobileOpen(true)}>
              <Menu size={18} />
            </button>
            <button
              className="hidden rounded-lg p-2 text-slate-400 hover:bg-white/5 md:block"
              onClick={() => setCollapsed((c) => !c)}
            >
              {collapsed ? <Menu size={18} /> : <X size={18} />}
            </button>
            <div className="hidden items-center gap-2 text-xs text-slate-500 sm:flex">
              <span className="flex items-center gap-1.5 rounded-full border border-mint/20 bg-mint/10 px-2.5 py-1 font-medium text-mint">
                <span className={clsx("h-1.5 w-1.5 rounded-full", online ? "bg-mint" : "bg-warn")} />
                {online ? "Live" : "Offline"}
              </span>
              <span className="flex items-center gap-1.5 rounded-full border border-brand/20 bg-brand/10 px-2.5 py-1 font-medium text-brand">
                <GitBranch size={12} /> Secure Aggregation Active
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="relative rounded-lg p-2 text-slate-400 hover:bg-white/5" title="Notifications">
              <Bell size={17} />
              <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-danger" />
            </button>
            <span className="hidden rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 font-mono text-[11px] text-slate-400 sm:block">
              {user?.email}
            </span>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function RealtimeChip({ text, tone = "bg-brand" }: { text: string; tone?: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[11px] text-slate-500">
      <span className={clsx("h-1.5 w-1.5 animate-pulse-slow rounded-full", tone)} />
      {text}
    </span>
  );
}
