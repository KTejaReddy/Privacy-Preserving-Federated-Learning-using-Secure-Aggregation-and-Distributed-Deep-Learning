import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Fingerprint, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { datasetApi, orgApi } from "../lib/api";
import { Badge, Button, Card, Empty, Field, Modal, PageHead, Stat, useToasts } from "../ui";
import { timeAgo } from "../lib/format";
import { Donut } from "../charts";

export default function Datasets() {
  const qc = useQueryClient();
  const { push, ui } = useToasts();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Record<string, string | number>>({});

  const { data: datasets } = useQuery({ queryKey: ["datasets"], queryFn: datasetApi.list });
  const { data: summary } = useQuery({ queryKey: ["datasets-summary"], queryFn: datasetApi.summary });
  const { data: orgs } = useQuery({ queryKey: ["orgs-min"], queryFn: () => orgApi.list() });
  const { data: schema } = useQuery({ queryKey: ["schema", form.feature_count ?? 8], queryFn: () => datasetApi.schema(Number(form.feature_count ?? 8)), enabled: open });

  const create = useMutation({
    mutationFn: () => datasetApi.create(form),
    onSuccess: () => {
      push("success", "Dataset registered · Data Guardian fingerprint generated");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["datasets"] });
      qc.invalidateQueries({ queryKey: ["datasets-summary"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const remove = useMutation({
    mutationFn: (id: number) => datasetApi.remove(id),
    onSuccess: () => {
      push("success", "Dataset removed");
      qc.invalidateQueries({ queryKey: ["datasets"] });
      qc.invalidateQueries({ queryKey: ["datasets-summary"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });

  const s = (summary ?? {}) as Record<string, unknown>;
  const byIndustry = (s.by_industry as Record<string, number>) ?? {};
  const donut = Object.entries(byIndustry).map(([name, value]) => ({ name, value }));

  return (
    <div>
      <PageHead
        title="Dataset Registry"
        desc="Governed dataset metadata. Raw data stays inside the organization — only synthetic fingerprints are shared."
        actions={
          <Button variant="primary" onClick={() => { setForm({ organization_id: 1, name: "", data_type: "tabular", feature_count: 8, sample_count: 1000, positive_ratio: 0.5, noise: 0.15 }); setOpen(true); }}>
            <Plus size={15} /> Register Dataset
          </Button>
        }
      />
      {ui}

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Datasets" value={s.total_datasets ?? 0} icon={<Database size={16} />} />
        <Stat label="Total Samples" value={Number(s.total_samples ?? 0).toLocaleString()} />
        <Stat label="Industries" value={Object.keys(byIndustry).length} />
        <Stat label="Fingerprint Protected" value="100%" sub="zero raw-data egress" icon={<Fingerprint size={16} />} />
      </div>

      {donut.length > 0 && (
        <Card className="mb-4" title="Samples by Industry">
          <div className="grid items-center gap-4 md:grid-cols-2">
            <Donut data={donut} height={200} />
            <div className="space-y-2">
              {Object.entries(byIndustry).map(([name, value]) => (
                <div key={name} className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">{name}</span>
                  <span className="font-mono text-slate-200">{Number(value).toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      <Card title={`${datasets?.length ?? 0} datasets`}>
        {!datasets?.length ? (
          <Empty title="No datasets registered" sub="Register a dataset to make it available for federated training." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="th">Dataset</th>
                  <th className="th">Organization</th>
                  <th className="th">Type</th>
                  <th className="th">Features</th>
                  <th className="th">Samples</th>
                  <th className="th">Noise</th>
                  <th className="th">Data Guardian</th>
                  <th className="th">Status</th>
                  <th className="th">Registered</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {datasets.map((d) => (
                  <tr key={d.id} className="row-hover">
                    <td className="td">
                      <p className="font-medium text-slate-200">{d.name}</p>
                      <p className="max-w-xs truncate text-[11px] text-slate-600">{d.description}</p>
                    </td>
                    <td className="td text-slate-400">{d.organization_name ?? "—"}</td>
                    <td className="td"><span className="badge bg-white/5 text-slate-400">{d.data_type}</span></td>
                    <td className="td font-mono text-slate-300">{d.feature_count}</td>
                    <td className="td font-mono text-slate-300">{d.sample_count.toLocaleString()}</td>
                    <td className="td font-mono text-slate-400">{d.noise}</td>
                    <td className="td">
                      <span className="flex items-center gap-1.5 text-[11px] text-mint">
                        <ShieldCheck size={13} />
                        {String(d.privacy_controls.fingerprint ?? "").slice(0, 10)}
                      </span>
                    </td>
                    <td className="td"><Badge status={d.status} /></td>
                    <td className="td text-slate-500">{timeAgo(d.created_at)}</td>
                    <td className="td">
                      <button className="rounded p-1.5 text-slate-500 hover:bg-white/10 hover:text-danger" onClick={() => remove.mutate(d.id)}>
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title="Register Dataset" wide>
        <div className="space-y-3">
          <Field label="Name"><input className="input" value={form.name as string} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Cardiac Risk Cohort" /></Field>
          <Field label="Organization">
            <select className="input" value={form.organization_id as number} onChange={(e) => setForm({ ...form, organization_id: Number(e.target.value) })}>
              {orgs?.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Field label="Type">
              <select className="input" value={form.data_type as string} onChange={(e) => setForm({ ...form, data_type: e.target.value })}>
                {["tabular", "image", "text", "time_series"].map((t) => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Features"><input type="number" className="input" value={form.feature_count as number} onChange={(e) => setForm({ ...form, feature_count: Number(e.target.value) })} /></Field>
            <Field label="Samples"><input type="number" className="input" value={form.sample_count as number} onChange={(e) => setForm({ ...form, sample_count: Number(e.target.value) })} /></Field>
            <Field label="Noise"><input type="number" step="0.01" className="input" value={form.noise as number} onChange={(e) => setForm({ ...form, noise: Number(e.target.value) })} /></Field>
          </div>
          <Field label="Positive ratio"><input type="number" step="0.01" className="input" value={form.positive_ratio as number} onChange={(e) => setForm({ ...form, positive_ratio: Number(e.target.value) })} /></Field>
          {schema && (
            <div>
              <p className="label">Derived schema ({schema.feature_names.length} features)</p>
              <div className="flex flex-wrap gap-1.5">
                {schema.feature_names.map((f) => (
                  <span key={f} className="rounded-md border border-white/10 bg-white/5 px-2 py-1 font-mono text-[11px] text-slate-400">{f}</span>
                ))}
              </div>
            </div>
          )}
          <p className="rounded-lg border border-mint/20 bg-mint/5 px-3 py-2 text-[11px] text-mint">
            Data Guardian: a deterministic SHA-256 fingerprint is derived from dataset metadata. No raw data is uploaded or shared.
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <Button onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" disabled={!form.name || create.isPending} onClick={() => create.mutate()}>
              {create.isPending ? "Registering…" : "Register dataset"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
