import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, CheckCheck, Play, Rocket, RotateCcw } from "lucide-react";
import { InferenceResult, modelApi, xaiApi } from "../lib/api";
import { Badge, Button, Card, Empty, Field, PageHead, Stat, useToasts } from "../ui";
import { pct, timeAgo } from "../lib/format";
import { useAuth } from "../auth";

const FEATURE_NAMES = ["account_age", "balance", "transactions", "credit_score", "risk_factor", "engagement", "geo_density", "support_tickets"];

export default function Models() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const { push, ui } = useToasts();
  const [infer, setInfer] = useState<InferenceResult | null>(null);
  const [features, setFeatures] = useState<number[]>([0.5, 1.2, -0.8, 0.3, 2.1, -1.4, 0.9, 0.2]);
  const [explanation, setExplanation] = useState<Record<string, unknown> | null>(null);

  const { data: versions } = useQuery({ queryKey: ["models"], queryFn: () => modelApi.list() });
  const { data: stats } = useQuery({ queryKey: ["model-stats"], queryFn: modelApi.stats });

  const approve = useMutation({
    mutationFn: (id: number) => modelApi.approve(id, "Approved via registry"),
    onSuccess: () => { push("success", "Version approved"); qc.invalidateQueries({ queryKey: ["models"] }); qc.invalidateQueries({ queryKey: ["model-stats"] }); },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const deploy = useMutation({
    mutationFn: (id: number) => modelApi.deploy(id, "Deployed to production"),
    onSuccess: () => { push("success", "Version deployed — active inference model updated"); qc.invalidateQueries({ queryKey: ["models"] }); qc.invalidateQueries({ queryKey: ["model-stats"] }); },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const rollback = useMutation({
    mutationFn: (id: number) => modelApi.rollback(id, "Rolled back"),
    onSuccess: () => { push("success", "Rolled back to parent version"); qc.invalidateQueries({ queryKey: ["models"] }); qc.invalidateQueries({ queryKey: ["model-stats"] }); },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });

  const runInfer = async () => {
    try {
      const r = await modelApi.infer(features);
      setInfer(r);
      setExplanation((r.explanation as Record<string, unknown>) ?? null);
    } catch (e) {
      push("error", e instanceof Error ? e.message : "Inference failed");
    }
  };

  const s = (stats ?? {}) as Record<string, unknown>;
  const best = (s.best_model as Record<string, unknown>) ?? null;

  return (
    <div>
      <PageHead title="Global Model Registry" desc="Version control, approval workflow, deployment and rollback of the global federated model." />
      {ui}

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Versions" value={s.total_versions ?? 0} icon={<Boxes size={16} />} />
        <Stat label="Deployed" value={s.deployed ?? 0} tone="text-mint" />
        <Stat label="Pending Approval" value={s.pending_approval ?? 0} tone="text-warn" />
        <Stat label="Best F1" value={best ? `${Number(best.f1).toFixed(3)}` : "—"} sub={best ? `v${Number(best.version)}` : undefined} />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" title="Model Versions" subtitle="One version per completed training job">
          {!versions?.length ? (
            <Empty title="No model versions" sub="Complete a training job to generate version 1." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="th">Version</th>
                    <th className="th">Job</th>
                    <th className="th">Accuracy</th>
                    <th className="th">Precision</th>
                    <th className="th">Recall</th>
                    <th className="th">F1</th>
                    <th className="th">Status</th>
                    <th className="th">Created</th>
                    <th className="th">Workflow</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {versions.map((v) => (
                    <tr key={v.id} className="row-hover">
                      <td className="td">
                        <span className="rounded-lg bg-gradient-to-br from-brand/20 to-brand-violet/20 px-2 py-1 font-mono font-bold text-brand">v{v.version}</span>
                      </td>
                      <td className="td text-slate-400">{v.job_name ?? `job-${v.job_id}`}</td>
                      <td className="td font-semibold text-slate-200">{pct(v.accuracy)}</td>
                      <td className="td font-mono text-slate-400">{v.precision?.toFixed(3) ?? "—"}</td>
                      <td className="td font-mono text-slate-400">{v.recall?.toFixed(3) ?? "—"}</td>
                      <td className="td font-mono text-slate-400">{v.f1?.toFixed(3) ?? "—"}</td>
                      <td className="td"><Badge status={v.status} /></td>
                      <td className="td text-slate-500">{timeAgo(v.created_at)}</td>
                      <td className="td">
                        <div className="flex gap-1">
                          {can("models:deploy") && v.status === "pending" && (
                            <Button size="sm" onClick={() => approve.mutate(v.id)}><CheckCheck size={12} /> Approve</Button>
                          )}
                          {can("models:deploy") && v.status === "approved" && (
                            <Button size="sm" variant="primary" onClick={() => deploy.mutate(v.id)}><Rocket size={12} /> Deploy</Button>
                          )}
                          {can("models:deploy") && v.status === "deployed" && v.parent_version != null && (
                            <Button size="sm" onClick={() => rollback.mutate(v.id)}><RotateCcw size={12} /> Rollback</Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Inference Playground" subtitle="Real predictions from the deployed global model">
          <div className="space-y-2.5">
            {FEATURE_NAMES.map((f, i) => (
              <div key={f}>
                <label className="label">{f}</label>
                <input type="number" step="0.1" className="input font-mono" value={features[i]} onChange={(e) => setFeatures((prev) => prev.map((x, j) => (j === i ? Number(e.target.value) : x)))} />
              </div>
            ))}
            <Button variant="primary" className="w-full" onClick={runInfer}>
              <Play size={14} /> Run inference
            </Button>
            {infer && (
              <div className="rounded-xl border border-brand/20 bg-brand/5 p-3.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">{infer.model_name as string}</span>
                  <Badge status={infer.prediction === 1 ? "positive" : "negative"} />
                </div>
                <div className="mt-2 flex items-end gap-4">
                  <div>
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">Probability</p>
                    <p className="text-xl font-bold text-brand">{(infer.probability as number).toFixed(4)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">Confidence</p>
                    <p className="text-xl font-bold text-mint">{pct(infer.confidence as number)}</p>
                  </div>
                </div>
                {explanation && (
                  <div className="mt-3 border-t border-white/10 pt-2.5">
                    <p className="mb-1 text-[10px] uppercase tracking-wide text-slate-500">Explanation ({explanation.method as string})</p>
                    <p className="text-[11px] leading-relaxed text-slate-400">{explanation.explanation as string}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
