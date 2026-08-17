import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, KeyRound, Lock, Play, ShieldCheck, Sigma } from "lucide-react";
import { coordinatorApi, analyticsApi } from "../lib/api";
import { Button, Card, Empty, Field, PageHead, Stat, useToasts } from "../ui";
import { pct } from "../lib/format";
import { BarsChart } from "../charts";

export default function Aggregation() {
  const qc = useQueryClient();
  const { push, ui } = useToasts();
  const [clients, setClients] = useState(4);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const { data: logs } = useQuery({ queryKey: ["agg-logs"], queryFn: coordinatorApi.aggregationLogs, refetchInterval: 4000 });
  const { data: privacy } = useQuery({ queryKey: ["privacy"], queryFn: analyticsApi.privacy });

  const run = useMutation({
    mutationFn: () => coordinatorApi.aggregationDemo({ clients }),
    onSuccess: (r) => {
      setResult(r);
      push("success", "Secure aggregation handshake completed");
      qc.invalidateQueries({ queryKey: ["agg-logs"] });
      qc.invalidateQueries({ queryKey: ["privacy"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });

  const p = (privacy ?? {}) as Record<string, number>;
  const steps: { icon: React.ReactNode; title: string; detail: string }[] = [
    { icon: <KeyRound size={16} />, title: "Pairwise mask agreement", detail: "Each ordered client pair derives a shared HMAC-SHA256 seed from the platform master secret." },
    { icon: <Lock size={16} />, title: "Client-side masking", detail: "Each client adds its outgoing masks (+) and subtracts incoming masks (−) to its local delta." },
    { icon: <ShieldCheck size={16} />, title: "Signature + encryption", detail: "Deltas are RSA-SHA256 signed and AES-256-GCM encrypted before upload." },
    { icon: <Sigma size={16} />, title: "Server unmask + sum", detail: "The server verifies signatures, cancels masks and sums — pairwise masks cancel exactly." },
    { icon: <BadgeCheck size={16} />, title: "Integrity verification", detail: "Math verification asserts sum-of-masked == sum-of-true-deltas within 1e-6." },
  ];

  return (
    <div>
      <PageHead
        title="Secure Aggregation Engine"
        desc="Bonawitz-style masked aggregation: no individual client update is ever visible to the server."
      />
      {ui}

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Budget Total" value={`${p.budget_total ?? 8.0}`} sub="privacy budget ε" />
        <Stat label="Budget Used" value={p.budget_used ?? 0} tone="text-warn" />
        <Stat label="Remaining" value={p.budget_remaining ?? 8.0} tone="text-mint" />
        <Stat label="Utilization" value={pct((p.utilization_pct ?? 0) / 100)} tone="text-danger" />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Live Handshake Demonstration" subtitle="Run a real masked aggregation on fresh engine deltas">
          <div className="space-y-4">
            <Field label="Participating clients">
              <input type="range" min={2} max={8} value={clients} onChange={(e) => setClients(Number(e.target.value))} className="w-full accent-cyan-400" />
              <p className="mt-1 text-xs text-slate-500">{clients} clients · {clients * (clients - 1)} pairwise masks</p>
            </Field>
            <Button variant="primary" className="w-full" disabled={run.isPending} onClick={() => run.mutate()}>
              <Play size={14} /> {run.isPending ? "Executing handshake…" : "Run secure aggregation"}
            </Button>

            {result && (
              <div className="space-y-3 rounded-xl border border-mint/20 bg-mint/5 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-mint">✓ Handshake verified</p>
                  <span className="badge border border-mint/30 bg-mint/10 text-mint">{result.method as string}</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="rounded-lg bg-white/5 p-2">
                    <p className="text-lg font-bold text-brand">{result.mask_pairs as number}</p>
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">mask pairs</p>
                  </div>
                  <div className="rounded-lg bg-white/5 p-2">
                    <p className="text-lg font-bold text-mint">{result.verified_signatures as number}</p>
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">verified</p>
                  </div>
                  <div className="rounded-lg bg-white/5 p-2">
                    <p className="text-lg font-bold text-brand-violet">{(result.math_ok as boolean) ? "YES" : "NO"}</p>
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">math check</p>
                  </div>
                </div>
                <div className="space-y-1.5">
                  {(result.log as string[])?.map((l, i) => (
                    <p key={i} className="font-mono text-[11px] text-slate-400">› {l}</p>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>

        <Card className="xl:col-span-2" title="Protocol Pipeline" subtitle="The secure aggregation flow">
          <div className="space-y-3">
            {steps.map((s, i) => (
              <div key={s.title} className="flex gap-3 rounded-xl border border-white/5 bg-white/[0.02] p-3.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-brand/20 to-brand-violet/20 text-brand">
                  {s.icon}
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-200">
                    <span className="mr-2 font-mono text-xs text-slate-500">{i + 1}</span>
                    {s.title}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">{s.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card title="Aggregation Logs" subtitle="Every aggregation run recorded in the audit trail">
          {!logs?.length ? (
            <Empty title="No aggregation logs yet" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="th">Run</th>
                    <th className="th">Method</th>
                    <th className="th">Clients</th>
                    <th className="th">Masked</th>
                    <th className="th">Masks Cancelled</th>
                    <th className="th">Sig Verified</th>
                    <th className="th">ε Consumed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {logs.map((l) => (
                    <tr key={l.id as number} className="row-hover">
                      <td className="td font-mono text-slate-400">#{l.id as number}</td>
                      <td className="td"><span className="badge bg-white/5 text-slate-400">{l.method as string}</span></td>
                      <td className="td">{l.client_count as number}</td>
                      <td className="td">{l.masked_upload_count as number}</td>
                      <td className="td">{l.masks_cancelled ? "✓" : "✗"}</td>
                      <td className="td">{l.signature_verified ? "✓" : "✗"}</td>
                      <td className="td font-mono text-slate-400">{l.privacy_budget_consumed as number}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Privacy Budget Consumption" subtitle="Per-round ε across the platform">
          {(logs ?? []).length ? (
            <BarsChart
              data={((logs ?? []) as { privacy_budget_consumed: number }[]).slice(0, 14).reverse().map((l, i) => ({ run: `#${i + 1}`, ε: l.privacy_budget_consumed }))}
              xKey="run"
              bars={[{ key: "ε", color: "#fbbf24" }]}
            />
          ) : (
            <Empty title="No data" />
          )}
        </Card>
      </div>
    </div>
  );
}
