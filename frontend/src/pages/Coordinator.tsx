import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ListChecks, XCircle } from "lucide-react";
import { coordinatorApi } from "../lib/api";
import { Badge, Button, Card, Empty, PageHead, Stat, useToasts } from "../ui";
import { CurveChart } from "../charts";
import { pct, timeAgo } from "../lib/format";
import { useAuth } from "../auth";

export default function Coordinator() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const { push, ui } = useToasts();

  const { data: overview } = useQuery({ queryKey: ["coord-overview"], queryFn: coordinatorApi.overview, refetchInterval: 4000 });
  const { data: approvals } = useQuery({ queryKey: ["coord-approvals"], queryFn: coordinatorApi.approvals, refetchInterval: 4000 });

  const decide = useMutation({
    mutationFn: ({ id, action }: { id: number; action: string }) => coordinatorApi.approve(id, action, "Reviewed by coordinator"),
    onSuccess: (_, v) => {
      push("success", `Job ${v.action}d`);
      qc.invalidateQueries({ queryKey: ["coord-approvals"] });
      qc.invalidateQueries({ queryKey: ["coord-overview"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });

  const o = (overview ?? {}) as Record<string, unknown>;
  const recent = (o.recent_rounds as { round_number: number; accuracy: number | null }[]) ?? [];
  const series = recent.slice().reverse().map((r) => ({ round: `R${r.round_number}`, accuracy: r.accuracy ?? 0 }));

  return (
    <div>
      <PageHead
        title="Federated Coordinator"
        desc="Orchestrate federated rounds across organizations and approve training runs."
      />
      {ui}

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Organizations" value={o.organizations ?? 0} />
        <Stat label="Total Jobs" value={o.jobs ?? 0} />
        <Stat label="Running" value={o.running_jobs ?? 0} tone="text-brand" />
        <Stat label="Rounds Total" value={o.rounds_total ?? 0} />
        <Stat label="Pending Approval" value={o.pending_approval ?? 0} tone="text-warn" />
        <Stat label="Avg Recent Acc" value={recent.length ? pct(recent.reduce((s, r) => s + (r.accuracy ?? 0), 0) / recent.length) : "—"} />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Approval Queue" subtitle="Jobs awaiting coordinator sign-off">
          {!approvals?.length ? (
            <Empty title="Queue is clear" sub="No jobs waiting for approval." icon={<CheckCircle2 size={28} />} />
          ) : (
            <div className="divide-y divide-white/5">
              {approvals.map((j) => (
                <div key={j.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-200">{j.name}</p>
                    <p className="text-[11px] text-slate-500">{j.algorithm} · {j.total_rounds} rounds · lr {j.learning_rate}</p>
                  </div>
                  {can("training:approve") ? (
                    <div className="flex shrink-0 gap-1.5">
                      <Button variant="primary" size="sm" onClick={() => decide.mutate({ id: j.id, action: "approve" })}>
                        <CheckCircle2 size={13} /> Approve
                      </Button>
                      <Button size="sm" onClick={() => decide.mutate({ id: j.id, action: "reject" })}>
                        <XCircle size={13} /> Reject
                      </Button>
                    </div>
                  ) : (
                    <Badge status={j.status} />
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Recent Round Accuracy" subtitle="Latest completed rounds across all jobs">
          {series.length ? <CurveChart data={series} xKey="round" lines={[{ key: "accuracy", color: "#a78bfa" }]} /> : <Empty title="No rounds yet" />}
        </Card>
      </div>

      <Card className="mt-4" title="Coordination Workflow" subtitle="How the coordinator drives a federated round">
        <div className="grid gap-3 md:grid-cols-5">
          {[
            { n: "1", t: "Select clients", d: "Random fraction of online nodes per round" },
            { n: "2", t: "Broadcast weights", d: "Global model pushed over simulated mTLS channels" },
            { n: "3", t: "Local training", d: "Each node trains on its private partition" },
            { n: "4", t: "Masked uploads", d: "Deltas masked, signed and AES-256 encrypted" },
            { n: "5", t: "Aggregate & evaluate", d: "Server cancels masks, applies FedAvg/FedProx/FedAdam" },
          ].map((s) => (
            <div key={s.n} className="rounded-xl border border-white/5 bg-white/[0.02] p-3.5">
              <div className="mb-2 flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-brand/30 to-brand-violet/30 text-xs font-bold text-brand">
                {s.n}
              </div>
              <p className="text-sm font-semibold text-slate-200">{s.t}</p>
              <p className="mt-1 text-[11px] leading-snug text-slate-500">{s.d}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
