import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { auditApi } from "../lib/api";
import { Badge, Button, Card, Empty, Field, PageHead, Stat } from "../ui";
import { dateTime } from "../lib/format";

export default function Audit() {
  const [action, setAction] = useState("");
  const [severity, setSeverity] = useState("");
  const { data: logs } = useQuery({
    queryKey: ["audit", action, severity],
    queryFn: () => auditApi.logs(`?action=${encodeURIComponent(action)}&severity=${encodeURIComponent(severity)}`),
  });
  const { data: summary } = useQuery({ queryKey: ["audit-summary"], queryFn: auditApi.summary });
  const { data: verify } = useQuery({ queryKey: ["audit-verify"], queryFn: auditApi.verify });
  const [checked, setChecked] = useState(false);

  const s = (summary ?? {}) as Record<string, unknown>;
  const records = ((logs?.records as Record<string, unknown>[]) ?? []);
  const bySeverity = (s.by_severity as Record<string, number>) ?? {};

  return (
    <div>
      <PageHead
        title="Audit Center"
        desc="Immutable append-only audit log. Every record is hash-chained to its predecessor — tampering is detectable."
        actions={
          <Button size="sm" onClick={() => setChecked(true)}>
            <ShieldCheck size={13} /> Verify chain integrity
          </Button>
        }
      />
      {checked && verify && (
        <div className={`mb-4 rounded-xl border p-4 ${verify.ok ? "border-mint/25 bg-mint/5" : "border-danger/25 bg-danger/10"}`}>
          <p className={`text-sm font-semibold ${verify.ok ? "text-mint" : "text-danger"}`}>
            {verify.ok ? "✓ " : "✗ "}{verify.message}
          </p>
        </div>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Total Records" value={s.total ?? 0} />
        <Stat label="Warnings" value={s.warnings ?? 0} tone="text-warn" />
        <Stat label="Info" value={bySeverity.info ?? 0} />
        <Stat label="Chain Integrity" value={verify?.ok ? "VERIFIED" : "Pending"} tone={verify?.ok ? "text-mint" : "text-slate-300"} />
      </div>

      <Card
        title="Audit Log"
        actions={
          <div className="flex gap-2">
            <input className="input w-52" placeholder="Filter by action…" value={action} onChange={(e) => setAction(e.target.value)} />
            <select className="input w-36" value={severity} onChange={(e) => setSeverity(e.target.value)}>
              <option value="">All severities</option>
              <option>info</option>
              <option>warning</option>
              <option>critical</option>
            </select>
          </div>
        }
      >
        {!records.length ? (
          <Empty title="No audit records" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="th">#</th>
                  <th className="th">Timestamp</th>
                  <th className="th">Actor</th>
                  <th className="th">Action</th>
                  <th className="th">Entity</th>
                  <th className="th">Details</th>
                  <th className="th">Severity</th>
                  <th className="th">Chain Hash</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {records.map((r) => (
                  <tr key={r.id as number} className="row-hover">
                    <td className="td font-mono text-slate-500">#{r.id as number}</td>
                    <td className="td font-mono text-[12px] text-slate-400">{dateTime(r.created_at as string)}</td>
                    <td className="td text-slate-300">{r.actor_email as string}</td>
                    <td className="td">
                      <span className="badge bg-white/5 font-mono text-slate-300">{r.action as string}</span>
                    </td>
                    <td className="td text-[12px] text-slate-500">{(r.entity_type as string) || "—"}{(r.entity_id as string) ? ` · ${r.entity_id}` : ""}</td>
                    <td className="td">
                      <span className="max-w-40 truncate font-mono text-[11px] text-slate-500">{JSON.stringify(r.details).slice(0, 44)}</span>
                    </td>
                    <td className="td"><Badge status={r.severity as string} /></td>
                    <td className="td font-mono text-[10px] text-slate-600">{(r.chain_hash as string).slice(0, 10)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
