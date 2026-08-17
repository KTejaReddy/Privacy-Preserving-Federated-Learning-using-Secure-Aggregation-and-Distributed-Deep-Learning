import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus, Trash2, Pencil } from "lucide-react";
import { orgApi } from "../lib/api";
import { Badge, Button, Card, Empty, Field, Modal, PageHead, Stat, useToasts } from "../ui";
import { timeAgo } from "../lib/format";
import { useAuth } from "../auth";

export default function Organizations() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const { push, ui } = useToasts();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Record<string, unknown> | null>(null);
  const [form, setForm] = useState<Record<string, string | boolean>>({});

  const { data, isLoading } = useQuery({ queryKey: ["orgs", q], queryFn: () => orgApi.list(q) });
  const { data: stats } = useQuery({ queryKey: ["org-stats"], queryFn: orgApi.stats });

  const save = useMutation({
    mutationFn: () =>
      editing ? orgApi.update(editing.id as number, form) : orgApi.create(form),
    onSuccess: () => {
      push("success", editing ? "Organization updated" : "Organization registered");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["orgs"] });
      qc.invalidateQueries({ queryKey: ["org-stats"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const remove = useMutation({
    mutationFn: (id: number) => orgApi.remove(id),
    onSuccess: () => {
      push("success", "Organization deleted");
      qc.invalidateQueries({ queryKey: ["orgs"] });
      qc.invalidateQueries({ queryKey: ["org-stats"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });

  const openCreate = () => {
    setEditing(null);
    setForm({ name: "", industry: "Technology", country: "", description: "", compliance_level: "GDPR + HIPAA aligned" });
    setOpen(true);
  };
  const openEdit = (o: Record<string, unknown>) => {
    setEditing(o);
    setForm({ name: o.name as string, industry: (o.industry as string) ?? "", country: (o.country as string) ?? "", description: (o.description as string) ?? "", compliance_level: (o.compliance_level as string) ?? "" });
    setOpen(true);
  };

  return (
    <div>
      <PageHead
        title="Organization Manager"
        desc="Participating organizations in the federated network. Raw data never leaves an organization."
        actions={
          can("orgs:manage") ? (
            <Button variant="primary" onClick={openCreate}>
              <Plus size={15} /> Register Organization
            </Button>
          ) : undefined
        }
      />
      {ui}

      {stats && (
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Organizations" value={stats.total as number} icon={<Building2 size={16} />} />
          <Stat label="Active" value={stats.active as number} tone="text-mint" />
          <Stat label="Federated Nodes" value={stats.total_nodes as number} />
          <Stat label="Registered Datasets" value={stats.total_datasets as number} />
        </div>
      )}

      <Card
        title={`${data?.length ?? 0} organizations`}
        actions={<input className="input w-56" placeholder="Search by name…" value={q} onChange={(e) => setQ(e.target.value)} />}
      >
        {isLoading ? (
          <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-12 animate-pulse rounded-lg bg-white/5" />)}</div>
        ) : !data?.length ? (
          <Empty title="No organizations" sub="Register the first organization to start the federation." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="th">Organization</th>
                  <th className="th">Industry</th>
                  <th className="th">Compliance</th>
                  <th className="th">Nodes</th>
                  <th className="th">Datasets</th>
                  <th className="th">Status</th>
                  <th className="th">Registered</th>
                  {can("orgs:manage") && <th className="th" />}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data.map((o) => (
                  <tr key={o.id} className="row-hover">
                    <td className="td">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand/25 to-brand-violet/25 text-xs font-bold text-brand">
                          {o.name.slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-slate-200">{o.name}</p>
                          <p className="text-[11px] text-slate-500">{o.country}</p>
                        </div>
                      </div>
                    </td>
                    <td className="td">{o.industry}</td>
                    <td className="td">
                      <span className="badge border border-brand/20 bg-brand/10 text-brand">{o.compliance_level}</span>
                    </td>
                    <td className="td font-semibold text-slate-200">{o.node_count}</td>
                    <td className="td font-semibold text-slate-200">{o.dataset_count}</td>
                    <td className="td"><Badge status={o.status} /></td>
                    <td className="td text-slate-500">{timeAgo(o.created_at)}</td>
                    {can("orgs:manage") && (
                      <td className="td">
                        <div className="flex justify-end gap-1">
                          <button className="rounded p-1.5 text-slate-500 hover:bg-white/10 hover:text-brand" onClick={() => openEdit(o as unknown as Record<string, unknown>)}>
                            <Pencil size={14} />
                          </button>
                          <button className="rounded p-1.5 text-slate-500 hover:bg-white/10 hover:text-danger" onClick={() => remove.mutate(o.id)}>
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? "Edit Organization" : "Register Organization"}>
        <div className="space-y-3">
          <Field label="Name"><input className="input" value={form.name as string} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Industry">
              <select className="input" value={form.industry as string} onChange={(e) => setForm({ ...form, industry: e.target.value })}>
                {["Technology", "Health & Care", "Banking & Finance", "Research & Academia", "Smart City", "Defense & Security", "Insurance", "Manufacturing"].map((i) => <option key={i}>{i}</option>)}
              </select>
            </Field>
            <Field label="Country"><input className="input" value={form.country as string} onChange={(e) => setForm({ ...form, country: e.target.value })} /></Field>
          </div>
          <Field label="Compliance Level">
            <select className="input" value={form.compliance_level as string} onChange={(e) => setForm({ ...form, compliance_level: e.target.value })}>
              {["GDPR + HIPAA aligned", "GDPR aligned", "MAS + GDPR aligned", "ISO 27001 + ITAR", "Custom"].map((c) => <option key={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Description"><textarea className="input min-h-20" value={form.description as string} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" disabled={!form.name || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? "Saving…" : editing ? "Save changes" : "Register"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
