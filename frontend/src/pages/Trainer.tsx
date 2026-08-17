import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Rocket, Target } from "lucide-react";
import { datasetApi, trainingApi } from "../lib/api";
import { useAuth } from "../auth";
import { Badge, Button, Card, Field, PageHead, Stat, useToasts } from "../ui";
import { pct } from "../lib/format";
import { CurveChart } from "../charts";

export default function Trainer() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { push, ui } = useToasts();
  const [form, setForm] = useState<Record<string, unknown>>({
    name: `${user?.organization_name ?? "My Org"} Quick Training`,
    algorithm: "fedavg",
    total_rounds: 5,
    client_fraction: 0.5,
    learning_rate: 0.05,
    local_epochs: 2,
    secure_aggregation: true,
    data_distribution: "non_iid",
    input_dim: 8,
  });

  const { data: myDatasets } = useQuery({ queryKey: ["trainer-datasets"], queryFn: datasetApi.list });
  const { data: myJobs } = useQuery({ queryKey: ["trainer-jobs"], queryFn: trainingApi.list, refetchInterval: 4000 });

  const launch = useMutation({
    mutationFn: () => trainingApi.create(form),
    onSuccess: async (job) => {
      await trainingApi.action(job.id, "start");
      push("success", `Training job "${job.name}" launched — rounds executing`);
      qc.invalidateQueries({ queryKey: ["trainer-jobs"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });

  const completed = (myJobs ?? []).filter((j) => j.status === "completed");
  const accuracySeries = completed.map((j) => ({ job: j.name.slice(0, 14), accuracy: (j.metrics_json.final_accuracy as number) ?? 0 }));
  const running = (myJobs ?? []).filter((j) => j.status === "running" || j.status === "approved").length;

  return (
    <div>
      <PageHead
        title="Trainer Mode"
        desc="Launch a federated training run in one click. Your organization's data stays local — only encrypted model updates travel."
      />
      {ui}

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="My Datasets" value={myDatasets?.length ?? 0} icon={<Target size={16} />} />
        <Stat label="My Jobs" value={myJobs?.length ?? 0} />
        <Stat label="Running Now" value={running} tone="text-brand" />
        <Stat label="Best Accuracy" value={pct(Math.max(...completed.map((j) => (j.metrics_json.final_accuracy as number) ?? 0), 0))} tone="text-mint" />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Quick Launch" subtitle="Configure and run instantly">
          <div className="space-y-3">
            <Field label="Job name"><input className="input" value={form.name as string} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Algorithm">
                <select className="input" value={form.algorithm as string} onChange={(e) => setForm({ ...form, algorithm: e.target.value })}>
                  {["fedavg", "fedprox", "fedadam"].map((a) => <option key={a}>{a}</option>)}
                </select>
              </Field>
              <Field label="Rounds"><input type="number" className="input" value={form.total_rounds as number} onChange={(e) => setForm({ ...form, total_rounds: Number(e.target.value) })} /></Field>
              <Field label="Client fraction"><input type="number" step="0.1" className="input" value={form.client_fraction as number} onChange={(e) => setForm({ ...form, client_fraction: Number(e.target.value) })} /></Field>
              <Field label="Learning rate"><input type="number" step="0.005" className="input" value={form.learning_rate as number} onChange={(e) => setForm({ ...form, learning_rate: Number(e.target.value) })} /></Field>
              <Field label="Data distribution">
                <select className="input" value={form.data_distribution as string} onChange={(e) => setForm({ ...form, data_distribution: e.target.value })}>
                  {["iid", "non_iid", "pathological"].map((d) => <option key={d}>{d}</option>)}
                </select>
              </Field>
              <Field label="Input features"><input type="number" className="input" value={form.input_dim as number} onChange={(e) => setForm({ ...form, input_dim: Number(e.target.value) })} /></Field>
            </div>
            <label className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2.5">
              <input type="checkbox" checked={form.secure_aggregation as boolean} onChange={(e) => setForm({ ...form, secure_aggregation: e.target.checked })} className="h-4 w-4 accent-cyan-400" />
              <span className="text-sm text-slate-200">Encrypt & mask updates (secure aggregation)</span>
            </label>
            <Button variant="primary" className="w-full" disabled={launch.isPending} onClick={() => launch.mutate()}>
              <Rocket size={14} /> {launch.isPending ? "Launching…" : "Launch training run"}
            </Button>
          </div>
        </Card>

        <Card title="My Training Performance" subtitle="Final accuracy per completed job">
          {accuracySeries.length ? (
            <CurveChart data={accuracySeries} xKey="job" lines={[{ key: "accuracy", color: "#22d3ee", name: "Accuracy" }]} />
          ) : (
            <div className="py-10 text-center text-sm text-slate-500">No completed jobs yet — launch your first run.</div>
          )}
          <div className="mt-4 divide-y divide-white/5">
            {(myJobs ?? []).slice(0, 5).map((j) => (
              <div key={j.id} className="flex items-center justify-between py-2.5">
                <div>
                  <p className="text-sm font-medium text-slate-200">{j.name}</p>
                  <p className="text-[11px] text-slate-500">{j.algorithm} · {j.current_round}/{j.total_rounds} rounds</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-semibold text-slate-300">{pct(j.metrics_json.final_accuracy as number)}</span>
                  <Badge status={j.status} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
