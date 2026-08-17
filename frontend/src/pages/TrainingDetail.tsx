import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { trainingApi } from "../lib/api";
import { Badge, Card, Empty, PageHead, Stat } from "../ui";
import { CurveChart } from "../charts";
import { bytes, ms, pct } from "../lib/format";

export default function TrainingDetail() {
  const { id } = useParams();
  const jobId = Number(id);
  const { data: job } = useQuery({ queryKey: ["job", jobId], queryFn: () => trainingApi.get(jobId), refetchInterval: 3000 });
  const { data: rounds } = useQuery({ queryKey: ["job-rounds", jobId], queryFn: () => trainingApi.rounds(jobId), refetchInterval: 3000 });

  if (!job) return <Empty title="Loading job…" />;

  const accData = (rounds ?? []).map((r) => ({ round: `R${r.round_number}`, accuracy: r.accuracy ?? 0, loss: r.avg_loss ?? 0 }));

  return (
    <div className="space-y-5">
      <Link to="/training" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-brand">
        <ArrowLeft size={15} /> Training Center
      </Link>
      <PageHead
        title={job.name}
        desc={job.description || "Federated training job"}
        actions={<Badge status={job.status} />}
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Algorithm" value={job.algorithm} accent="bg-brand" />
        <Stat label="Rounds" value={`${job.current_round}/${job.total_rounds}`} />
        <Stat label="Client Fraction" value={`${Math.round(job.client_fraction * 100)}%`} />
        <Stat label="Learning Rate" value={job.learning_rate} />
        <Stat label="Local Epochs" value={job.local_epochs} />
        <Stat label="Final Accuracy" value={pct(job.metrics_json.final_accuracy as number)} tone="text-mint" />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Global Accuracy per Round">
          {accData.length ? <CurveChart data={accData} xKey="round" lines={[{ key: "accuracy", color: "#22d3ee", name: "Accuracy" }]} /> : <Empty title="No rounds yet" sub="Rounds appear here as the job executes." />}
        </Card>
        <Card title="Global Loss per Round">
          {accData.length ? <CurveChart data={accData} xKey="round" lines={[{ key: "loss", color: "#f87171", name: "Loss" }]} /> : <Empty title="No rounds yet" />}
        </Card>
      </div>

      <Card title="Round History" subtitle="Per-round metrics persisted after each aggregation">
        {!rounds?.length ? (
          <Empty title="No completed rounds" sub="This job has not executed rounds yet." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="th">Round</th>
                  <th className="th">Clients</th>
                  <th className="th">Accuracy</th>
                  <th className="th">Precision</th>
                  <th className="th">Recall</th>
                  <th className="th">F1</th>
                  <th className="th">Loss</th>
                  <th className="th">Communication</th>
                  <th className="th">Agg. Time</th>
                  <th className="th">Privacy ε</th>
                  <th className="th">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {rounds.map((r) => (
                  <tr key={r.id} className="row-hover">
                    <td className="td font-mono font-semibold text-brand">R{r.round_number}</td>
                    <td className="td">{r.participated_count}</td>
                    <td className="td font-semibold text-slate-200">{pct(r.accuracy)}</td>
                    <td className="td font-mono text-slate-400">{r.precision?.toFixed(3) ?? "—"}</td>
                    <td className="td font-mono text-slate-400">{r.recall?.toFixed(3) ?? "—"}</td>
                    <td className="td font-mono text-slate-400">{r.f1?.toFixed(3) ?? "—"}</td>
                    <td className="td font-mono text-slate-400">{r.avg_loss?.toFixed(4) ?? "—"}</td>
                    <td className="td font-mono text-slate-400">{bytes(r.communication_bytes)}</td>
                    <td className="td font-mono text-slate-400">{ms(r.aggregation_time_ms)}</td>
                    <td className="td font-mono text-slate-400">{r.privacy_budget_used}</td>
                    <td className="td"><Badge status={r.status} /></td>
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
