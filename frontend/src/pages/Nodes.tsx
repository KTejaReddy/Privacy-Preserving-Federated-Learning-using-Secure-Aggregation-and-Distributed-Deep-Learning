import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cpu, Gauge, Network, Plus, ShieldCheck, Trash2, Wifi } from "lucide-react";
import { nodeApi, orgApi } from "../lib/api";
import { Badge, Button, Card, Empty, Field, Modal, PageHead, Stat, useToasts } from "../ui";
import { pct, timeAgo } from "../lib/format";

export default function Nodes() {
  const qc = useQueryClient();
  const { push, ui } = useToasts();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Record<string, string | number>>({});

  const { data: nodes } = useQuery({ queryKey: ["nodes"], queryFn: nodeApi.list });
  const { data: health } = useQuery({ queryKey: ["nodes-health"], queryFn: nodeApi.health, refetchInterval: 5000 });
  const { data: orgs } = useQuery({ queryKey: ["orgs-min"], queryFn: () => orgApi.list() });

  const create = useMutation({
    mutationFn: () => nodeApi.create(form),
    onSuccess: () => {
      push("success", "Node registered · mTLS certificate issued");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["nodes"] });
      qc.invalidateQueries({ queryKey: ["nodes-health"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const remove = useMutation({
    mutationFn: (id: number) => nodeApi.remove(id),
    onSuccess: () => {
      push("success", "Node removed");
      qc.invalidateQueries({ queryKey: ["nodes"] });
      qc.invalidateQueries({ queryKey: ["nodes-health"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });

  const h = (health ?? {}) as Record<string, number>;
  return (
    <div>
      <PageHead
        title="Federated Node Manager"
        desc="Registered compute endpoints. Each node holds its organization's data and trains locally."
        actions={
          <Button variant="primary" onClick={() => { setForm({ organization_id: 1, name: "", device_type: "server", cpu_cores: 8, ram_gb: 32, bandwidth_mbps: 400, latency_ms: 10 }); setOpen(true); }}>
            <Plus size={15} /> Register Node
          </Button>
        }
      />
      {ui}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Total Nodes" value={h.total ?? 0} icon={<Network size={16} />} />
        <Stat label="Online" value={h.online ?? 0} tone="text-mint" />
        <Stat label="Degraded" value={h.degraded ?? 0} tone="text-warn" />
        <Stat label="Offline" value={h.offline ?? 0} tone="text-danger" />
        <Stat label="Avg Latency" value={`${h.avg_latency_ms ?? 0} ms`} sub="realtime" />
        <Stat label="mTLS Verified" value={`${h.mtls_verified ?? 0}/${h.total ?? 0}`} icon={<ShieldCheck size={16} />} />
      </div>

      <Card title={`${nodes?.length ?? 0} federated nodes`} subtitle="Status updates streamed every 3s">
        {!nodes?.length ? (
          <Empty title="No nodes registered" sub="Register a node to join the federation." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="th">Node</th>
                  <th className="th">Organization</th>
                  <th className="th">Device</th>
                  <th className="th">Compute</th>
                  <th className="th">Latency</th>
                  <th className="th">Bandwidth</th>
                  <th className="th">Trust</th>
                  <th className="th">mTLS</th>
                  <th className="th">Status</th>
                  <th className="th">Heartbeat</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {nodes.map((n) => (
                  <tr key={n.id} className="row-hover">
                    <td className="td">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${n.status === "online" ? "bg-mint" : n.status === "degraded" ? "bg-warn" : n.status === "offline" ? "bg-danger" : "bg-slate-500"} ${n.status === "online" ? "animate-pulse" : ""}`} />
                        <div>
                          <p className="font-medium text-slate-200">{n.name}</p>
                          <p className="font-mono text-[10px] text-slate-600">{n.endpoint}</p>
                        </div>
                      </div>
                    </td>
                    <td className="td text-slate-400">{n.organization_name ?? "—"}</td>
                    <td className="td"><span className="badge bg-white/5 text-slate-400">{n.device_type}</span></td>
                    <td className="td text-slate-400">
                      <span className="flex items-center gap-1"><Cpu size={12} /> {n.cpu_cores}c</span>
                      <span className="block text-[11px] text-slate-600">{n.gpu_name !== "None" ? n.gpu_name : `${n.ram_gb} GB`}</span>
                    </td>
                    <td className="td font-mono text-slate-300">{n.latency_ms} ms</td>
                    <td className="td font-mono text-slate-300">{n.bandwidth_mbps} Mbps</td>
                    <td className="td font-mono" style={{ color: n.trust_score > 0.85 ? "#34d399" : "#fbbf24" }}>{pct(n.trust_score)}</td>
                    <td className="td">
                      {n.mTLS_verified ? <ShieldCheck size={15} className="text-mint" /> : <span className="text-slate-600">—</span>}
                    </td>
                    <td className="td"><Badge status={n.status} /></td>
                    <td className="td text-slate-500">{timeAgo(n.last_heartbeat ?? n.created_at)}</td>
                    <td className="td">
                      <button className="rounded p-1.5 text-slate-500 hover:bg-white/10 hover:text-danger" onClick={() => remove.mutate(n.id)}>
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

      <Modal open={open} onClose={() => setOpen(false)} title="Register Federated Node">
        <div className="space-y-3">
          <Field label="Name"><input className="input" value={form.name as string} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. hospital-icu-01" /></Field>
          <Field label="Organization">
            <select className="input" value={form.organization_id as number} onChange={(e) => setForm({ ...form, organization_id: Number(e.target.value) })}>
              {orgs?.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </Field>
          <Field label="Device Type">
            <select className="input" value={form.device_type as string} onChange={(e) => setForm({ ...form, device_type: e.target.value })}>
              {["server", "gpu", "edge", "mobile"].map((d) => <option key={d}>{d}</option>)}
            </select>
          </Field>
          <div className="grid grid-cols-3 gap-3">
            <Field label="CPU cores"><input type="number" className="input" value={form.cpu_cores as number} onChange={(e) => setForm({ ...form, cpu_cores: Number(e.target.value) })} /></Field>
            <Field label="RAM (GB)"><input type="number" className="input" value={form.ram_gb as number} onChange={(e) => setForm({ ...form, ram_gb: Number(e.target.value) })} /></Field>
            <Field label="GPU"><input className="input" value={(form.gpu_name as string) ?? ""} onChange={(e) => setForm({ ...form, gpu_name: e.target.value })} placeholder="A100 / None" /></Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Bandwidth (Mbps)"><input type="number" className="input" value={form.bandwidth_mbps as number} onChange={(e) => setForm({ ...form, bandwidth_mbps: Number(e.target.value) })} /></Field>
            <Field label="Latency (ms)"><input type="number" className="input" value={form.latency_ms as number} onChange={(e) => setForm({ ...form, latency_ms: Number(e.target.value) })} /></Field>
          </div>
          <p className="flex items-center gap-1.5 text-[11px] text-slate-500">
            <Wifi size={12} className="text-brand" /> On registration the node receives an RSA identity and a simulated mTLS certificate (AES-256-GCM cipher suite).
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <Button onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" disabled={!form.name || create.isPending} onClick={() => create.mutate()}>
              {create.isPending ? "Issuing certificate…" : "Register node"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
