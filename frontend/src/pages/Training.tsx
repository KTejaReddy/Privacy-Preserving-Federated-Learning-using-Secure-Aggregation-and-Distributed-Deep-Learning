import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Plus, Rocket, StopCircle, Trash2 } from "lucide-react";
import { trainingApi } from "../lib/api";
import { Badge, Button, Card, Empty, Field, Modal, PageHead, Stat, useToasts } from "../ui";
import { pct, timeAgo } from "../lib/format";
import { useAuth } from "../auth";

const ALGORITHMS = [
  { key: "fedavg", label: "FedAvg", desc: "Weighted average of client deltas (McMahan 2017)" },
  { key: "fedprox", label: "FedProx", desc: "Proximal term for heterogeneous data (Li 2020)" },
  { key: "fedadam", label: "FedAdam", desc: "Server-side Adam optimizer (Reddi 2021)" },
];

export default function Training() {
  const { can, user } = useAuth();
  const qc = useQueryClient();
  const { push, ui } = useToasts();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Record<string, unknown>>({
    name: "",
    algorithm: "fedavg",
    total_rounds: 8,
    client_fraction: 0.6,
    learning_rate: 0.05,
    local_epochs: 2,
    secure_aggregation: true,
    data_distribution: "non_iid",
    input_dim: 8,
    batch_size: 32,
    mu: 0.05,
    server_momentum: 0.9,
  });

  const { data: jobs } = useQuery({ queryKey: ["jobs"], queryFn: trainingApi.list, refetchInterval: 4000 });
  const { data: stats } = useQuery({ queryKey: ["job-stats"], queryFn: trainingApi.stats, refetchInterval: 5000 });

  const create = useMutation({
    mutationFn: () => trainingApi.create(form),
    onSuccess: () => {
      push("success", "Training job created");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job-stats"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const act = useMutation({
    mutationFn: ({ id, action }: { id: number; action: string }) => trainingApi.action(id, action),
    onSuccess: (_, v) => {
      push("info", `Job ${v.action}`);
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job-stats"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const remove = useMutation({
    mutationFn: (id: number) => trainingApi.remove(id),
    onSuccess: () => {
      push("success", "Job deleted");
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job-stats"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });

  const s = (stats ?? {}) as Record<string, number>;
  const canRun = can("training:run");

  return (
    <div>
      <PageHead
        title="Training Center"
        desc="Create and run federated training jobs with configurable aggregation algorithms and secure aggregation."
        actions={
          can("training:create") ? (
            <Button variant="primary" onClick={() => setOpen(true)}>
              <Plus size={15} /> New Training Job
            </Button>
          ) : undefined
        }
      />
      {ui}

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Total Jobs" value={s.total ?? 0} />
        <Stat label="Running" value={s.running ?? 0} tone="text-brand" />
        <Stat label="Completed" value={s.completed ?? 0} tone="text-mint" />
        <Stat label="Failed" value={s.failed ?? 0} tone="text-danger" />
        <Stat label="Rounds Executed" value={s.total_rounds_executed ?? 0} />
        <Stat label="Avg Accuracy" value={pct(s.avg_accuracy)} />
      </div>

      <Card title={`${jobs?.length ?? 0} training jobs`} subtitle="Auto-refreshes every 4s">
        {!jobs?.length ? (
          <Empty title="No training jobs" sub="Create your first federated training job." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="th">Job</th>
                  <th className="th">Algorithm</th>
                  <th className="th">Progress</th>
                  <th className="th">Rounds</th>
                  <th className="th">Secure Agg.</th>
                  <th className="th">Accuracy</th>
                  <th className="th">Status</th>
                  <th className="th">Created</th>
                  <th className="th">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {jobs.map((j) => (
                  <tr key={j.id} className="row-hover">
                    <td className="td">
                      <Link to={`/training/${j.id}`} className="font-medium text-slate-200 hover:text-brand">
                        {j.name}
                      </Link>
                      <p className="text-[11px] text-slate-600">{j.description || "—"}</p>
                    </td>
                    <td className="td">
                      <span className="badge border border-brand/20 bg-brand/10 text-brand">{j.algorithm}</span>
                    </td>
                    <td className="td">
                      <div className="w-28">
                        <div className="mb-1 flex justify-between text-[10px] text-slate-500">
                          <span>{j.current_round}/{j.total_rounds}</span>
                          <span>{Math.round((j.current_round / j.total_rounds) * 100)}%</span>
                        </div>
                        <div className="h-1 overflow-hidden rounded-full bg-white/5">
                          <div className="h-full bg-gradient-to-r from-brand to-mint transition-all" style={{ width: `${(j.current_round / j.total_rounds) * 100}%` }} />
                        </div>
                      </div>
                    </td>
                    <td className="td font-mono text-slate-400">{j.total_rounds}</td>
                    <td className="td">{j.secure_aggregation ? <span className="text-mint">●</span> : <span className="text-slate-600">○</span>}</td>
                    <td className="td font-semibold text-slate-200">{pct(j.metrics_json.final_accuracy as number)}</td>
                    <td className="td"><Badge status={j.status} /></td>
                    <td className="td text-slate-500">{timeAgo(j.created_at)}</td>
                    <td className="td">
                      <div className="flex gap-1">
                        {canRun && j.status === "draft" && (
                          <button title="Start" className="rounded p-1.5 text-mint hover:bg-mint/10" onClick={() => act.mutate({ id: j.id, action: "start" })}>
                            <Play size={14} />
                          </button>
                        )}
                        {canRun && (j.status === "running" || j.status === "approved") && (
                          <button title="Cancel" className="rounded p-1.5 text-warn hover:bg-warn/10" onClick={() => act.mutate({ id: j.id, action: "cancel" })}>
                            <StopCircle size={14} />
                          </button>
                        )}
                        {can("training:manage") && (
                          <button title="Delete" className="rounded p-1.5 text-slate-500 hover:bg-danger/10 hover:text-danger" onClick={() => remove.mutate(j.id)}>
                            <Trash2 size={14} />
                          </button>
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

      <Modal open={open} onClose={() => setOpen(false)} title="Create Federated Training Job" wide>
        <div className="space-y-4">
          <Field label="Job name"><input className="input" value={form.name as string} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Global Fraud Risk Model" /></Field>
          <div>
            <p className="label">Aggregation algorithm</p>
            <div className="grid gap-2 md:grid-cols-3">
              {ALGORITHMS.map((a) => (
                <button
                  key={a.key}
                  onClick={() => setForm({ ...form, algorithm: a.key })}
                  className={`rounded-xl border p-3 text-left transition ${form.algorithm === a.key ? "border-brand/50 bg-brand/10" : "border-white/10 bg-white/[0.02] hover:border-white/25"}`}
                >
                  <p className={`text-sm font-semibold ${form.algorithm === a.key ? "text-brand" : "text-slate-200"}`}>{a.label}</p>
                  <p className="mt-1 text-[11px] leading-snug text-slate-500">{a.desc}</p>
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Field label="Rounds"><input type="number" className="input" value={form.total_rounds as number} onChange={(e) => setForm({ ...form, total_rounds: Number(e.target.value) })} /></Field>
            <Field label="Client fraction"><input type="number" step="0.1" className="input" value={form.client_fraction as number} onChange={(e) => setForm({ ...form, client_fraction: Number(e.target.value) })} /></Field>
            <Field label="Learning rate"><input type="number" step="0.005" className="input" value={form.learning_rate as number} onChange={(e) => setForm({ ...form, learning_rate: Number(e.target.value) })} /></Field>
            <Field label="Local epochs"><input type="number" className="input" value={form.local_epochs as number} onChange={(e) => setForm({ ...form, local_epochs: Number(e.target.value) })} /></Field>
            <Field label="Batch size"><input type="number" className="input" value={form.batch_size as number} onChange={(e) => setForm({ ...form, batch_size: Number(e.target.value) })} /></Field>
            <Field label="FedProx μ"><input type="number" step="0.01" className="input" value={form.mu as number} onChange={(e) => setForm({ ...form, mu: Number(e.target.value) })} /></Field>
            <Field label="Distribution">
              <select className="input" value={form.data_distribution as string} onChange={(e) => setForm({ ...form, data_distribution: e.target.value })}>
                {["iid", "non_iid", "pathological"].map((d) => <option key={d}>{d}</option>)}
              </select>
            </Field>
            <Field label="Input features"><input type="number" className="input" value={form.input_dim as number} onChange={(e) => setForm({ ...form, input_dim: Number(e.target.value) })} /></Field>
          </div>
          <label className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2.5">
            <input type="checkbox" checked={form.secure_aggregation as boolean} onChange={(e) => setForm({ ...form, secure_aggregation: e.target.checked })} className="h-4 w-4 accent-cyan-400" />
            <div>
              <p className="text-sm font-medium text-slate-200">Enable Secure Aggregation</p>
              <p className="text-[11px] text-slate-500">Masked updates + RSA signatures + AES-256-GCM transport encryption</p>
            </div>
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" disabled={!form.name || create.isPending} onClick={() => create.mutate()}>
              <Rocket size={14} /> {create.isPending ? "Creating…" : "Create job"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
