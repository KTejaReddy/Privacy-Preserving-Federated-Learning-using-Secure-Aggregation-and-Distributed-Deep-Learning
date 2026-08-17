import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { evalApi, modelApi } from "../lib/api";
import { Card, Empty, PageHead, Stat, Tabs } from "../ui";
import { BarsChart, CurveChart } from "../charts";
import { pct } from "../lib/format";

export default function Evaluation() {
  const [tab, setTab] = useState("summary");
  const { data: summary } = useQuery({ queryKey: ["eval-summary"], queryFn: evalApi.summary });
  const { data: versions } = useQuery({ queryKey: ["models"], queryFn: () => modelApi.list() });
  const { data: compare } = useQuery({
    queryKey: ["eval-compare"],
    queryFn: () => evalApi.compare((versions ?? []).slice(0, 4).map((v) => v.id)),
    enabled: (versions ?? []).length > 0,
  });
  const [confId, setConfId] = useState<number | null>(null);
  const { data: confusion } = useQuery({
    queryKey: ["confusion", confId],
    queryFn: () => evalApi.confusion(confId!),
    enabled: confId != null,
  });

  const s = (summary ?? {}) as Record<string, number>;
  const hist = (summary?.accuracy_history as { version: number; accuracy: number | null; f1: number | null }[]) ?? [];
  const compareRows = ((compare?.rows as Record<string, unknown>[]) ?? []).map((r) => ({
    name: `v${r.version as number}`,
    accuracy: (r.accuracy as number) ?? 0,
    precision: (r.precision as number) ?? 0,
    recall: (r.recall as number) ?? 0,
    f1: (r.f1 as number) ?? 0,
  }));
  const best = compare?.best as Record<string, unknown> | undefined;

  const matrix = confusion?.matrix as number[][] | undefined;
  const tp = matrix?.[0]?.[0] ?? 0, fn = matrix?.[0]?.[1] ?? 0, fp = matrix?.[1]?.[0] ?? 0, tn = matrix?.[1]?.[1] ?? 0;

  return (
    <div>
      <PageHead title="Model Evaluation Center" desc="Precision, recall, F1, AUC and confusion analysis of every global model version." />

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Best Accuracy" value={pct(s.best_accuracy)} tone="text-mint" />
        <Stat label="Best F1" value={s.best_f1?.toFixed(3) ?? "—"} />
        <Stat label="Avg Precision" value={s.average_precision?.toFixed(3) ?? "—"} />
        <Stat label="Avg Recall" value={s.average_recall?.toFixed(3) ?? "—"} />
      </div>

      <div className="mb-4">
        <Tabs tabs={[{ key: "summary", label: "Accuracy History" }, { key: "compare", label: "Version Comparison" }, { key: "confusion", label: "Confusion Matrix" }]} value={tab} onChange={setTab} />
      </div>

      {tab === "summary" && (
        <Card title="Model Accuracy Across Versions">
          {hist.length ? (
            <CurveChart data={hist} xKey="version" lines={[{ key: "accuracy", color: "#22d3ee", name: "Accuracy" }, { key: "f1", color: "#a78bfa", name: "F1" }]} />
          ) : (
            <Empty title="No evaluation data" />
          )}
        </Card>
      )}

      {tab === "compare" && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card title="Metric Comparison" subtitle="Accuracy · Precision · Recall · F1 per version">
            {compareRows.length ? (
              <BarsChart
                data={compareRows}
                xKey="name"
                bars={[
                  { key: "accuracy", color: "#22d3ee" },
                  { key: "precision", color: "#a78bfa" },
                  { key: "recall", color: "#34d399" },
                  { key: "f1", color: "#fbbf24" },
                ]}
              />
            ) : (
              <Empty title="Select versions to compare" />
            )}
          </Card>
          <Card title="Version Leaderboard">
            {compareRows.length ? (
              <div className="space-y-2">
                {compareRows.map((r, i) => (
                  <div key={r.name} className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 ${best && String(best.version) === r.name.slice(1) ? "border-mint/30 bg-mint/5" : "border-white/5 bg-white/[0.02]"}`}>
                    <span className="w-6 text-sm font-bold text-slate-500">#{i + 1}</span>
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-slate-200">{r.name}</p>
                      <div className="mt-1 flex gap-3 text-[11px] text-slate-500">
                        <span>acc {pct(r.accuracy, 0)}</span>
                        <span>P {r.precision.toFixed(2)}</span>
                        <span>R {r.recall.toFixed(2)}</span>
                        <span>F1 {r.f1.toFixed(2)}</span>
                      </div>
                    </div>
                    {best && String(best.version) === r.name.slice(1) && <span className="badge border border-mint/30 bg-mint/10 text-mint">BEST</span>}
                  </div>
                ))}
              </div>
            ) : (
              <Empty title="No versions to compare" />
            )}
          </Card>
        </div>
      )}

      {tab === "confusion" && (
        <Card
          title="Confusion Matrix"
          actions={
            <select className="input w-56" value={confId ?? ""} onChange={(e) => setConfId(Number(e.target.value))}>
              <option value="">Select a version…</option>
              {versions?.map((v) => (
                <option key={v.id} value={v.id}>v{v.version} · {v.job_name ?? `job-${v.job_id}`}</option>
              ))}
            </select>
          }
        >
          {matrix ? (
            <div className="flex flex-wrap items-center gap-8">
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-xl border border-mint/25 bg-mint/10 p-6 text-center">
                  <p className="text-2xl font-bold text-mint">{tp}</p>
                  <p className="text-[10px] uppercase text-slate-500">True Positive</p>
                </div>
                <div className="rounded-xl border border-danger/25 bg-danger/10 p-6 text-center">
                  <p className="text-2xl font-bold text-danger">{fn}</p>
                  <p className="text-[10px] uppercase text-slate-500">False Negative</p>
                </div>
                <div className="rounded-xl border border-warn/25 bg-warn/10 p-6 text-center">
                  <p className="text-2xl font-bold text-warn">{fp}</p>
                  <p className="text-[10px] uppercase text-slate-500">False Positive</p>
                </div>
                <div className="rounded-xl border border-brand/25 bg-brand/10 p-6 text-center">
                  <p className="text-2xl font-bold text-brand">{tn}</p>
                  <p className="text-[10px] uppercase text-slate-500">True Negative</p>
                </div>
              </div>
              <div className="space-y-2">
                {(confusion?.metrics as Record<string, number> | undefined) &&
                  Object.entries(confusion?.metrics as Record<string, number>).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between gap-8 text-sm">
                      <span className="text-slate-400">{k}</span>
                      <span className="font-mono font-semibold text-slate-200">{v.toFixed(4)}</span>
                    </div>
                  ))}
              </div>
            </div>
          ) : (
            <Empty title="Select a version" sub="Reconstructs a confusion matrix from the version's global weights." />
          )}
        </Card>
      )}
    </div>
  );
}
