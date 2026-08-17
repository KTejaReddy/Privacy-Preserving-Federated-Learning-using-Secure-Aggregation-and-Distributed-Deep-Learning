import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Activity,
  Building2,
  Cpu,
  Database,
  Gauge,
  Layers,
  Network,
  ShieldCheck,
  TrendingUp,
  Boxes,
} from "lucide-react";
import { dashboardApi } from "../lib/api";
import { Badge, Card, Empty, PageHead, Stat } from "../ui";
import { AreaCurve, Donut } from "../charts";
import { bytes, pct, timeAgo, scoreColor } from "../lib/format";
import { useAuth } from "../auth";

export default function Dashboard() {
  const { user, roleLabel, featureFlags } = useAuth();
  const { data, isLoading } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });

  if (isLoading || !data) {
    return (
      <div>
        <PageHead title={`Welcome back, ${user?.full_name?.split(" ")[0] ?? "Researcher"}`} desc={roleLabel} />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="panel h-24 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const k = data.kpis as Record<string, number>;
  const accSeries = (data.accuracy_series as Record<string, unknown>[]) ?? [];
  const health = (data.node_health as Record<string, number>) ?? {};
  const feed = (data.activity_feed as { action: string; actor: string; severity: string; created_at: string }[]) ?? [];
  const recentJobs = (data.recent_jobs as Record<string, unknown>[]) ?? [];
  const topNodes = (data.top_nodes as { name: string; trust_score: number; status: string; latency_ms: number }[]) ?? [];

  const roleGreeting: Record<string, string> = {
    admin: "Full platform control is active. All systems nominal.",
    coordinator: "Federated rounds, organizations and approvals are under your control.",
    org_admin: "Your organization's datasets and local training are ready.",
    ml_engineer: "Models, evaluation and explainability tooling are available.",
    research_scientist: "The Federated Lab is ready for experiments.",
  };

  const healthData = Object.entries(health).map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-6">
      <PageHead
        title={`Welcome back, ${user?.full_name?.split(" ")[0] ?? "Researcher"}`}
        desc={roleGreeting[user?.role ?? ""] ?? "Enterprise federated AI control plane."}
        actions={
          featureFlags.secure_aggregation !== false ? (
            <span className="flex items-center gap-2 rounded-lg border border-mint/20 bg-mint/10 px-3 py-1.5 text-xs font-medium text-mint">
              <ShieldCheck size={14} /> Secure aggregation active
            </span>
          ) : undefined
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {[
          { label: "Organizations", value: k.organizations, icon: <Building2 size={16} /> },
          { label: "Nodes Online", value: `${k.nodes_online}/${k.nodes}`, icon: <Network size={16} /> },
          { label: "Datasets", value: k.datasets, icon: <Database size={16} /> },
          { label: "Jobs Completed", value: `${k.completed_jobs}/${k.jobs}`, icon: <Cpu size={16} /> },
          { label: "Rounds Executed", value: k.rounds, icon: <Activity size={16} /> },
          { label: "Deployed Models", value: k.deployed_models, icon: <Boxes size={16} /> },
        ].map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
            <Stat label={s.label} value={s.value} icon={s.icon} />
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Stat label="Avg Global Accuracy" value={pct(k.avg_accuracy)} tone={scoreColor(k.avg_accuracy ?? 0)} icon={<TrendingUp size={16} />} />
        <Stat label="Avg F1 Score" value={(k.avg_f1 ?? 0).toFixed(3)} tone="text-slate-100" icon={<Gauge size={16} />} />
        <Stat label="Privacy Budget Used" value={`${(k.privacy_budget_used ?? 0).toFixed(1)} / 8.0`} sub="cumulative ε across rounds" icon={<ShieldCheck size={16} />} />
        <Stat label="Model Versions" value={k.model_versions} sub={`${k.deployed_models} deployed`} icon={<Layers size={16} />} />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" title="Federated Accuracy · Global Model" subtitle="Accuracy per executed round across all jobs">
          {accSeries.length ? (
            <AreaCurve data={accSeries} xKey="round" series={[{ key: "accuracy", color: "#22d3ee", name: "Accuracy" }]} />
          ) : (
            <Empty title="No rounds yet" sub="Launch a training job to see the accuracy curve." />
          )}
        </Card>
        <Card title="Node Health">
          {healthData.some((h) => h.value > 0) ? (
            <Donut data={healthData} height={220} />
          ) : (
            <Empty title="No nodes registered" />
          )}
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Recent Jobs" subtitle="Latest federated training runs">
          {recentJobs.length ? (
            <div className="divide-y divide-white/5">
              {recentJobs.map((j) => (
                <div key={j.id as number} className="flex items-center justify-between py-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-200">{j.name as string}</p>
                    <p className="text-[11px] uppercase tracking-wide text-slate-500">{j.algorithm as string}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-slate-300">{pct(j.accuracy as number)}</span>
                    <Badge status={j.status as string} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <Empty title="No jobs yet" />
          )}
        </Card>
        <Card title="Activity Feed" subtitle="Live audit trail · last 24h">
          {feed.length ? (
            <div className="space-y-2.5">
              {feed.map((f, i) => (
                <div key={i} className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
                  <span
                    className={
                      f.severity === "warning" || f.severity === "critical"
                        ? "h-1.5 w-1.5 shrink-0 rounded-full bg-danger"
                        : "h-1.5 w-1.5 shrink-0 rounded-full bg-mint"
                    }
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-mono text-xs text-slate-300">{f.action}</p>
                    <p className="truncate text-[11px] text-slate-500">{f.actor}</p>
                  </div>
                  <span className="shrink-0 text-[11px] text-slate-500">{timeAgo(f.created_at)}</span>
                </div>
              ))}
            </div>
          ) : (
            <Empty title="No activity yet" />
          )}
        </Card>
      </div>

      {topNodes.length > 0 && (
        <Card title="Top Nodes by Trust Score" subtitle="Simulated mutual-TLS verified nodes">
          <div className="grid gap-2 md:grid-cols-3">
            {topNodes.map((n) => (
              <div key={n.name} className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-slate-200">{n.name}</p>
                  <Badge status={n.status} />
                </div>
                <div className="mt-2 flex justify-between text-[11px] text-slate-500">
                  <span>Trust {pct(n.trust_score)}</span>
                  <span>{n.latency_ms} ms</span>
                </div>
                <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/5">
                  <div className="h-full rounded-full bg-gradient-to-r from-brand to-mint" style={{ width: `${(n.trust_score ?? 0) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
