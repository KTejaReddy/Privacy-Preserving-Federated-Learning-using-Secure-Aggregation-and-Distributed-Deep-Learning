import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "../lib/api";
import { Card, Empty, PageHead, Stat } from "../ui";
import { BarsChart, CurveChart, Donut } from "../charts";
import { bytes, ms, pct, scoreColor } from "../lib/format";

export default function Analytics() {
  const { data } = useQuery({ queryKey: ["analytics"], queryFn: analyticsApi.overview, refetchInterval: 5000 });
  const { data: privacy } = useQuery({ queryKey: ["privacy"], queryFn: analyticsApi.privacy });

  const d = (data ?? {}) as Record<string, unknown>;
  const accHist = (d.accuracy_history as { round: number; accuracy: number | null; loss: number | null; f1: number | null }[]) ?? [];
  const commHist = (d.communication_history as { round: number; communication_bytes: number; aggregation_time_ms: number }[]) ?? [];
  const nodeContrib = (d.node_contribution as { node_id: number; rounds: number; avg_local_accuracy: number }[]) ?? [];
  const drift = (d.model_drift as { version: number; job_id: number; accuracy: number | null; f1: number | null }[]) ?? [];
  const jobsByAlgo = (d.jobs_by_algorithm as Record<string, number>) ?? {};
  const p = (privacy ?? {}) as Record<string, number>;

  const algoData = Object.entries(jobsByAlgo).map(([name, value]) => ({ name, value }));
  const commData = commHist.map((c) => ({ round: `R${c.round}`, MB: Number((c.communication_bytes / (1024 * 1024)).toFixed(3)), "agg ms": c.aggregation_time_ms }));

  return (
    <div>
      <PageHead title="Analytics" desc="Deep metrics across the federation: performance, communication, contribution, drift and privacy." />

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Rounds" value={d.total_rounds ?? 0} />
        <Stat label="Avg Accuracy" value={pct(d.avg_accuracy as number)} tone={scoreColor(d.avg_accuracy as number)} />
        <Stat label="Avg F1" value={(d.avg_f1 as number)?.toFixed(3) ?? "—"} />
        <Stat label="Communication" value={bytes(d.total_communication_bytes as number)} sub="total across rounds" />
        <Stat label="Aggregation Time" value={ms(d.total_aggregation_time_ms as number)} sub="cumulative" />
        <Stat label="Privacy ε Used" value={p.budget_used ?? d.privacy_budget_used_total ?? 0} tone="text-warn" sub={`of ${p.budget_total ?? 8}`} />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Federated Accuracy & Loss" subtitle="Per-round global model metrics">
          {accHist.length ? (
            <CurveChart data={accHist.map((r) => ({ round: `R${r.round}`, accuracy: r.accuracy ?? 0, loss: r.loss ?? 0 }))} xKey="round" lines={[{ key: "accuracy", color: "#22d3ee", name: "Accuracy" }, { key: "loss", color: "#f87171", name: "Loss" }]} />
          ) : <Empty title="No rounds yet" />}
        </Card>
        <Card title="Communication Cost per Round" subtitle="Bandwidth + aggregation latency">
          {commData.length ? (
            <BarsChart data={commData} xKey="round" bars={[{ key: "MB", color: "#a78bfa", name: "Payload (MB)" }]} />
          ) : <Empty title="No communication data" />}
        </Card>
        <Card title="Node Contribution" subtitle="Participation count and avg local accuracy">
          {nodeContrib.length ? (
            <BarsChart data={nodeContrib.map((n) => ({ node: `#${n.node_id}`, rounds: n.rounds, "avg local acc": n.avg_local_accuracy }))} xKey="node" bars={[{ key: "rounds", color: "#34d399", name: "Rounds" }]} />
          ) : <Empty title="No client updates yet" />}
        </Card>
        <Card title="Model Drift Across Versions" subtitle="Accuracy movement between versions">
          {drift.length ? (
            <CurveChart data={drift.map((v) => ({ version: `v${v.version}`, accuracy: v.accuracy ?? 0 }))} xKey="version" lines={[{ key: "accuracy", color: "#fbbf24", name: "Accuracy" }]} />
          ) : <Empty title="No versions" />}
        </Card>
        <Card title="Jobs by Algorithm">
          {algoData.some((a) => a.value > 0) ? <Donut data={algoData} height={220} /> : <Empty title="No jobs" />}
        </Card>
        <Card title="Privacy Budget" subtitle="Secure aggregation privacy accounting">
          {privacy ? (
            <div className="space-y-4">
              <div>
                <div className="mb-1 flex justify-between text-xs">
                  <span className="text-slate-400">Cumulative ε consumed</span>
                  <span className="font-mono text-slate-200">{p.budget_used} / {p.budget_total}</span>
                </div>
                <div className="h-3 overflow-hidden rounded-full bg-white/5">
                  <div className="h-full rounded-full bg-gradient-to-r from-mint via-warn to-danger" style={{ width: `${Math.min(100, p.utilization_pct ?? 0)}%` }} />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg bg-white/5 p-3">
                  <p className="text-lg font-bold text-mint">{p.budget_remaining}</p>
                  <p className="text-[10px] uppercase text-slate-500">remaining</p>
                </div>
                <div className="rounded-lg bg-white/5 p-3">
                  <p className="text-lg font-bold text-brand">{p.rounds_with_masking ?? 0}</p>
                  <p className="text-[10px] uppercase text-slate-500">masked rounds</p>
                </div>
                <div className="rounded-lg bg-white/5 p-3">
                  <p className="text-lg font-bold text-warn">{p.max_per_round}</p>
                  <p className="text-[10px] uppercase text-slate-500">max per round</p>
                </div>
              </div>
            </div>
          ) : <Empty title="No privacy data" />}
        </Card>
      </div>
    </div>
  );
}
