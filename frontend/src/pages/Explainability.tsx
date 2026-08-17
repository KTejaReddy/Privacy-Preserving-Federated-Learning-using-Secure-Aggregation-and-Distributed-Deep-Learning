import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BrainCircuit, Scale } from "lucide-react";
import { modelApi, xaiApi } from "../lib/api";
import { Badge, Card, Empty, Field, PageHead, Tabs } from "../ui";
import { BarsChart } from "../charts";
import { pct } from "../lib/format";

export default function Explainability() {
  const { data: versions } = useQuery({ queryKey: ["models"], queryFn: () => modelApi.list() });
  const defaultVersion = versions?.[0]?.id;
  const [versionId, setVersionId] = useState<number | null>(null);
  const [sample, setSample] = useState(0);
  const [tab, setTab] = useState("explain");
  const [sens, setSens] = useState("feature_0");
  const vid = versionId ?? defaultVersion;

  const { data: explain } = useQuery({
    queryKey: ["xai-explain", vid, sample],
    queryFn: () => xaiApi.explain(vid!, sample),
    enabled: vid != null,
  });
  const { data: importance } = useQuery({
    queryKey: ["xai-importance", vid],
    queryFn: () => xaiApi.importance(vid!),
    enabled: vid != null,
  });
  const { data: fairness } = useQuery({
    queryKey: ["xai-fairness", vid, sens],
    queryFn: () => xaiApi.fairness(vid!, sens),
    enabled: vid != null,
  });
  const { data: biasReport } = useQuery({ queryKey: ["xai-bias"], queryFn: xaiApi.biasReport });

  const contributions = (explain?.ranked_contributions as { feature: string; shap: number }[]) ?? [];
  const importances = (importance?.importances as { feature: string; importance: number }[]) ?? [];
  const groups = (fairness?.groups as { label: string; prediction_rate: number; positive_rate: number }[]) ?? [];

  const selection = (
    <div className="mb-4 flex flex-wrap items-end gap-3">
      <Field label="Model version">
        <select className="input w-64" value={vid ?? ""} onChange={(e) => setVersionId(Number(e.target.value))}>
          {versions?.map((v) => (
            <option key={v.id} value={v.id}>v{v.version} · {v.job_name ?? `job-${v.job_id}`}</option>
          ))}
        </select>
      </Field>
      {tab === "explain" && (
        <Field label="Sample index">
          <input type="number" className="input w-28" value={sample} onChange={(e) => setSample(Number(e.target.value))} />
        </Field>
      )}
      {tab === "fairness" && (
        <Field label="Sensitive attribute">
          <select className="input w-48" value={sens} onChange={(e) => setSens(e.target.value)}>
            {(explain?.feature_names as string[] | undefined)?.map((f) => <option key={f}>{f}</option>) ?? <option>feature_0</option>}
          </select>
        </Field>
      )}
    </div>
  );

  return (
    <div>
      <PageHead title="Explainable AI Center" desc="Kernel-SHAP local explanations, permutation importance, fairness and bias analysis of the global model." />
      {selection}
      <div className="mb-4">
        <Tabs
          tabs={[
            { key: "explain", label: "Local Explanation" },
            { key: "importance", label: "Global Importance" },
            { key: "fairness", label: "Fairness & Bias" },
            { key: "bias", label: "Bias Report" },
          ]}
          value={tab}
          onChange={setTab}
        />
      </div>

      {tab === "explain" && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card title="Prediction Explanation" subtitle={`Kernel-SHAP · sample #${explain?.sample_index ?? sample}`}>
            {explain ? (
              <div className="space-y-4">
                <div className="flex items-center justify-around rounded-xl border border-white/5 bg-white/[0.02] p-4">
                  <div className="text-center">
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">Prediction</p>
                    <p className={`text-2xl font-bold ${explain.predicted_class === 1 ? "text-mint" : "text-brand"}`}>
                      Class {(explain.predicted_class as number) === 1 ? "Positive" : "Negative"}
                    </p>
                    <p className="text-xs text-slate-500">p = {(explain.prediction as number).toFixed(4)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">Confidence</p>
                    <p className="text-2xl font-bold text-mint">{pct(explain.confidence as number)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">Base value</p>
                    <p className="text-2xl font-bold text-slate-300">{(explain.base_value as number).toFixed(3)}</p>
                  </div>
                </div>
                <div className="space-y-1.5">
                  {contributions.map((c) => {
                    const maxAbs = Math.max(...contributions.map((x) => Math.abs(x.shap)));
                    const w = (Math.abs(c.shap) / maxAbs) * 100;
                    return (
                      <div key={c.feature} className="flex items-center gap-3">
                        <span className="w-32 shrink-0 truncate font-mono text-[11px] text-slate-400">{c.feature}</span>
                        <div className="h-5 flex-1 overflow-hidden rounded-md bg-white/5">
                          <div
                            className={`h-full ${c.shap >= 0 ? "bg-gradient-to-r from-brand/70 to-brand" : "bg-gradient-to-r from-danger to-danger/70"}`}
                            style={{ width: `${Math.max(4, w)}%` }}
                          />
                        </div>
                        <span className={`w-16 shrink-0 text-right font-mono text-[11px] ${c.shap >= 0 ? "text-brand" : "text-danger"}`}>
                          {c.shap >= 0 ? "+" : ""}{c.shap.toFixed(3)}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <p className="rounded-lg border border-white/10 bg-white/[0.03] p-3 text-xs leading-relaxed text-slate-400">
                  {explain.explanation as string}
                </p>
              </div>
            ) : (
              <Empty title="Select a version" icon={<BrainCircuit size={26} />} />
            )}
          </Card>
          <Card title="Top Contributors" subtitle="Features ranked by |SHAP| magnitude">
            {contributions.length ? (
              <BarsChart
                data={contributions.slice(0, 6).map((c) => ({ feature: c.feature, "|SHAP|": Math.abs(c.shap) }))}
                xKey="feature"
                bars={[{ key: "|SHAP|", color: "#a78bfa" }]}
              />
            ) : (
              <Empty title="No data" />
            )}
          </Card>
        </div>
      )}

      {tab === "importance" && (
        <Card title="Global Feature Importance" subtitle="Permutation importance on a held-out reference set">
          {importances.length ? (
            <BarsChart
              data={importances.map((i) => ({ feature: i.feature, importance: i.importance }))}
              xKey="feature"
              bars={[{ key: "importance", color: "#22d3ee" }]}
              height={300}
            />
          ) : (
            <Empty title="Select a version" />
          )}
          {importance && <p className="mt-2 text-xs text-slate-500">Baseline accuracy: {pct(importance.baseline_accuracy as number)}</p>}
        </Card>
      )}

      {tab === "fairness" && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card title="Fairness Metrics" subtitle={`Sensitive attribute: ${sens}`}>
            {fairness ? (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-2 text-center">
                  {[
                    { l: "Demographic Parity", v: fairness.demographic_parity as number },
                    { l: "Equalized Odds", v: fairness.equalized_odds as number },
                    { l: "Disparate Impact", v: fairness.disparate_impact as number },
                  ].map((m) => (
                    <div key={m.l} className="rounded-lg bg-white/5 p-3">
                      <p className={`text-lg font-bold ${m.v >= 0.8 ? "text-mint" : m.v >= 0.6 ? "text-warn" : "text-danger"}`}>{m.v.toFixed(3)}</p>
                      <p className="text-[10px] uppercase tracking-wide text-slate-500">{m.l}</p>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  <Scale size={14} className={fairness.bias_level === "low" ? "text-mint" : "text-danger"} />
                  <Badge status={fairness.bias_level as string} />
                  <span className="text-xs text-slate-400">{fairness.bias_level === "low" ? "No significant bias detected" : "Disparate rates detected"}</span>
                </div>
                <p className="rounded-lg border border-white/10 bg-white/[0.03] p-3 text-xs text-slate-400">{fairness.interpretation as string}</p>
              </div>
            ) : (
              <Empty title="Select a version" />
            )}
          </Card>
          <Card title="Group Prediction Rates" subtitle="Positive-class prediction rate by group">
            {groups.length ? (
              <BarsChart
                data={groups.map((g) => ({ group: g.label, "prediction rate": g.prediction_rate, "true positive rate": g.positive_rate }))}
                xKey="group"
                bars={[
                  { key: "prediction rate", color: "#22d3ee" },
                  { key: "true positive rate", color: "#a78bfa" },
                ]}
              />
            ) : (
              <Empty title="No data" />
            )}
          </Card>
        </div>
      )}

      {tab === "bias" && (
        <Card title="Bias Report" subtitle="Aggregate fairness across the most recent evaluated versions">
          {biasReport ? (
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-mint/20 bg-mint/5 p-4 text-center">
                <p className="text-3xl font-bold text-mint">{biasReport.healthy as number}</p>
                <p className="text-xs text-slate-400">Healthy versions</p>
              </div>
              <div className="rounded-xl border border-danger/20 bg-danger/5 p-4 text-center">
                <p className="text-3xl font-bold text-danger">{biasReport.attention as number}</p>
                <p className="text-xs text-slate-400">Need attention</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 text-center">
                <p className="text-3xl font-bold text-slate-200">{(biasReport.reports as unknown[]).length}</p>
                <p className="text-xs text-slate-400">Versions audited</p>
              </div>
              <div className="md:col-span-3">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/5">
                      <th className="th">Version</th>
                      <th className="th">Demographic Parity</th>
                      <th className="th">Equalized Odds</th>
                      <th className="th">Disparate Impact</th>
                      <th className="th">Verdict</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {((biasReport.reports as Record<string, unknown>[]) ?? []).map((r, i) => (
                      <tr key={i} className="row-hover">
                        <td className="td font-mono text-brand">v{r.version as number}</td>
                        <td className="td font-mono text-slate-300">{(r.demographic_parity as number).toFixed(3)}</td>
                        <td className="td font-mono text-slate-300">{(r.equalized_odds as number).toFixed(3)}</td>
                        <td className="td font-mono text-slate-300">{(r.disparate_impact as number).toFixed(3)}</td>
                        <td className="td"><Badge status={r.bias_level as string} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <Empty title="No versions evaluated yet" />
          )}
        </Card>
      )}
    </div>
  );
}
