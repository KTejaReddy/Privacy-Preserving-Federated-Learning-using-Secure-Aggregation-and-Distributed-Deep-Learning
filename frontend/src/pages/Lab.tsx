import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Play, RefreshCw, Scale, ShieldCheck, Timer, TrendingUp, Users } from "lucide-react";
import { labApi } from "../lib/api";
import { Badge, Button, Card, Empty, Field, Modal, PageHead, Stat, Tabs, useToasts } from "../ui";
import { CurveChart, BarsChart } from "../charts";
import { bytes, pct, timeAgo } from "../lib/format";

const ALGOS = [
  { value: "fedavg", label: "FedAvg", desc: "Federated Averaging — weight deltas averaged, scaled by sample counts." },
  { value: "fedprox", label: "FedProx", desc: "Adds a proximal term to keep local models near the global model." },
  { value: "fedadam", label: "FedAdam", desc: "Server-side Adam optimizer over the aggregated gradient." },
];
const DISTS = [
  { value: "iid", label: "IID", desc: "Identical distribution across every client." },
  { value: "non_iid", label: "Non-IID", desc: "Each client sees a biased slice of the feature space." },
  { value: "pathological", label: "Pathological", desc: "Clients hold disjoint label classes — the hard case." },
];
const COLORS: Record<string, string> = { fedavg: "#22d3ee", fedprox: "#a78bfa", fedadam: "#34d399" };

export default function Lab() {
  const qc = useQueryClient();
  const { push, ui } = useToasts();
  const [tab, setTab] = useState("benchmark");
  const [bench, setBench] = useState({ distribution: "non_iid", clients: 8, rounds: 12 });
  const [run, setRun] = useState({
    name: "",
    description: "",
    algorithm: "fedavg",
    clients: 6,
    rounds: 10,
    data_distribution: "non_iid",
    node_failure_rate: 0.15,
  });
  const [viewing, setViewing] = useState<number | null>(null);

  const { data: experiments } = useQuery({ queryKey: ["lab-exp"], queryFn: labApi.list });
  const { data: detail } = useQuery({
    queryKey: ["lab-detail", viewing],
    queryFn: () => labApi.get(viewing as number),
    enabled: viewing != null,
  });
  const runBenchmark = useMutation({
    mutationFn: () => labApi.benchmark(bench.distribution, bench.clients, bench.rounds),
    onSuccess: () => {
      push("success", "Benchmark complete — three algorithms on identical data");
      qc.invalidateQueries({ queryKey: ["lab-exp"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Benchmark failed"),
  });
  // drop stale results whenever the benchmark configuration changes
  useEffect(() => {
    runBenchmark.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bench.distribution, bench.clients, bench.rounds]);
  const createExp = useMutation({
    mutationFn: () => labApi.create(run),
    onSuccess: () => {
      push("success", "Experiment finished — results saved to history");
      qc.invalidateQueries({ queryKey: ["lab-exp"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Experiment failed"),
  });

  const bData = runBenchmark.data as { distribution: string; results: Record<string, any> } | undefined;
  const results = bData?.results ?? {};
  const benchSeries = (["fedavg", "fedprox", "fedadam"] as const).filter((a) => results[a]).map((a) => ({ key: a, color: COLORS[a], name: a }));
  const curveData = buildCurve(results);
  const expList = (experiments ?? []) as any[];
  const d = detail as any;

  return (
    <div>
      <PageHead
        title="Federated Lab"
        desc="Interactive learning environment — run experiments, compare aggregation algorithms, and watch privacy-preserving training unfold."
        actions={
          <span className="flex items-center gap-2 rounded-full border border-mint/20 bg-mint/10 px-3 py-1.5 text-xs font-medium text-mint">
            <FlaskConical size={13} /> Research sandbox
          </span>
        }
      />
      {ui}

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Experiments" value={expList.length} icon={<FlaskConical size={18} />} />
        <Stat
          label="Benchmark"
          value={results.fedavg ? "Ready" : "Idle"}
          tone={results.fedavg ? "text-mint" : "text-slate-400"}
          sub="FedAvg vs FedProx vs FedAdam"
        />
        <Stat label="Algorithms" value="3" sub="FedAvg · FedProx · FedAdam" />
        <Stat label="Distributions" value="3" sub="IID · Non-IID · Pathological" />
      </div>

      <Tabs
        tabs={[
          { key: "benchmark", label: "Benchmark Studio" },
          { key: "run", label: "Run Experiment" },
          { key: "history", label: `History (${expList.length})` },
          { key: "learn", label: "Learn" },
        ]}
        value={tab}
        onChange={setTab}
      />

      <div className="mt-4">
        {tab === "benchmark" && (
          <div className="grid gap-4 xl:grid-cols-3">
            <Card title="Benchmark Configuration" subtitle="Same data, same clients — only the optimizer changes">
              <div className="space-y-4">
                <Field label="Data distribution">
                  <select
                    className="input"
                    value={bench.distribution}
                    onChange={(e) => setBench({ ...bench, distribution: e.target.value })}
                  >
                    {DISTS.map((d) => (
                      <option key={d.value} value={d.value}>
                        {d.label} — {d.desc}
                      </option>
                    ))}
                  </select>
                </Field>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Clients">
                    <input
                      type="number"
                      className="input"
                      min={2}
                      max={50}
                      value={bench.clients}
                      onChange={(e) => setBench({ ...bench, clients: Number(e.target.value) })}
                    />
                  </Field>
                  <Field label="Rounds">
                    <input
                      type="number"
                      className="input"
                      min={1}
                      max={50}
                      value={bench.rounds}
                      onChange={(e) => setBench({ ...bench, rounds: Number(e.target.value) })}
                    />
                  </Field>
                </div>
                <Button variant="primary" className="w-full justify-center" disabled={runBenchmark.isPending} onClick={() => runBenchmark.mutate()}>
                  {runBenchmark.isPending ? <RefreshCw size={15} className="animate-spin" /> : <Play size={15} />}
                  {runBenchmark.isPending ? "Running benchmark…" : "Run Benchmark"}
                </Button>
                <p className="text-[11px] leading-relaxed text-slate-500">
                  Each algorithm trains an identical MLP across the same encrypted federated rounds. Secure aggregation is
                  always on — deltas are masked, signed and AES-256 encrypted before the server ever sees them.
                </p>
              </div>
            </Card>

            <Card className="xl:col-span-2" title="Aggregation Algorithm Comparison" subtitle="Test accuracy per federated round">
              {benchSeries.length ? (
                <>
                  <CurveChart data={curveData} xKey="round" lines={benchSeries} height={280} />
                  <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
                    {(["fedavg", "fedprox", "fedadam"] as const).map((a) => {
                      const r = results[a];
                      if (!r) return null;
                      return (
                        <div key={a} className="rounded-xl border border-white/5 bg-white/[0.02] p-3.5">
                          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
                            <span className="h-2 w-2 rounded-full" style={{ background: COLORS[a] }} /> {a}
                          </p>
                          <p className="mt-1.5 text-xl font-bold tabular-nums text-slate-100">{pct(r.final_accuracy)}</p>
                          <p className="text-[11px] text-slate-500">final accuracy · {bytes(r.communication_bytes)} comm</p>
                        </div>
                      );
                    })}
                  </div>
                </>
              ) : (
                <Empty
                  icon={<Scale size={26} />}
                  title="No benchmark run yet"
                  sub="Configure the left panel and hit Run Benchmark to compare FedAvg, FedProx and FedAdam on identical data."
                />
              )}
            </Card>
          </div>
        )}

        {tab === "run" && (
          <div className="grid gap-4 xl:grid-cols-3">
            <Card title="New Experiment" subtitle="Design a federated run and watch it converge">
              <div className="space-y-4">
                <Field label="Experiment name">
                  <input className="input" placeholder="e.g. FedProx under pathological data" value={run.name} onChange={(e) => setRun({ ...run, name: e.target.value })} />
                </Field>
                <Field label="Description">
                  <textarea className="input min-h-[60px]" placeholder="What hypothesis are you testing?" value={run.description} onChange={(e) => setRun({ ...run, description: e.target.value })} />
                </Field>
                <Field label="Aggregation algorithm">
                  <div className="grid grid-cols-3 gap-1.5">
                    {ALGOS.map((a) => (
                      <button
                        key={a.value}
                        onClick={() => setRun({ ...run, algorithm: a.value })}
                        className={run.algorithm === a.value ? "btn-primary btn-sm justify-center" : "btn-ghost btn-sm justify-center"}
                        title={a.desc}
                      >
                        {a.label}
                      </button>
                    ))}
                  </div>
                </Field>
                <Field label="Data distribution">
                  <select className="input" value={run.data_distribution} onChange={(e) => setRun({ ...run, data_distribution: e.target.value })}>
                    {DISTS.map((d) => (
                      <option key={d.value} value={d.value}>
                        {d.label} — {d.desc}
                      </option>
                    ))}
                  </select>
                </Field>
                <div className="grid grid-cols-3 gap-3">
                  <Field label="Clients">
                    <input type="number" className="input" min={2} max={50} value={run.clients} onChange={(e) => setRun({ ...run, clients: Number(e.target.value) })} />
                  </Field>
                  <Field label="Rounds">
                    <input type="number" className="input" min={1} max={100} value={run.rounds} onChange={(e) => setRun({ ...run, rounds: Number(e.target.value) })} />
                  </Field>
                  <Field label="Fail rate">
                    <input type="number" className="input" min={0} max={0.9} step={0.05} value={run.node_failure_rate} onChange={(e) => setRun({ ...run, node_failure_rate: Number(e.target.value) })} />
                  </Field>
                </div>
                <Button variant="primary" className="w-full justify-center" disabled={createExp.isPending || !run.name.trim()} onClick={() => createExp.mutate()}>
                  {createExp.isPending ? <RefreshCw size={15} className="animate-spin" /> : <Play size={15} />}
                  {createExp.isPending ? "Training federated rounds…" : "Run Experiment"}
                </Button>
                {run.node_failure_rate > 0 && (
                  <p className="rounded-lg border border-warn/20 bg-warn/10 px-3 py-2 text-[11px] text-warn">
                    Node failures are simulated: {pct(run.node_failure_rate)} of rounds will drop a client, degrading the
                    accuracy curve — just like real stragglers in production federated networks.
                  </p>
                )}
              </div>
            </Card>

            <Card className="xl:col-span-2" title="Latest Experiment Result">
              {createExp.data ? (
                <LatestResult data={createExp.data as any} />
              ) : (
                <Empty
                  icon={<TrendingUp size={26} />}
                  title="Run your first experiment"
                  sub="Configure the experiment and press Run. The full per-round accuracy curve, communication cost and elapsed time appear here, then land in History."
                />
              )}
            </Card>
          </div>
        )}

        {tab === "history" && (
          <Card title="Experiment History" subtitle="Every run, immutable, with full results">
            {!expList.length ? (
              <Empty title="No experiments yet" sub="Run an experiment from the Run Experiment tab." icon={<FlaskConical size={26} />} />
            ) : (
              <div className="divide-y divide-white/5">
                {expList.map((e) => (
                  <div key={e.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <button className="text-sm font-semibold text-slate-200 hover:text-brand" onClick={() => setViewing(e.id)}>
                        {e.name}
                      </button>
                      <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-slate-500">
                        <Badge status={e.algorithm} /> {e.data_distribution} · {e.clients} clients · {e.rounds} rounds · {pct(e.node_failure_rate)} failures
                      </p>
                      <p className="text-[11px] text-slate-600">{timeAgo(e.created_at)}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="text-sm font-bold tabular-nums text-mint">{e.final_accuracy != null ? pct(e.final_accuracy) : "—"}</span>
                      <Button size="sm" onClick={() => setViewing(e.id)}>
                        View
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}

        {tab === "learn" && <LearnSection />}
      </div>

      <Modal open={viewing != null} onClose={() => setViewing(null)} title={d?.name ?? "Experiment"} wide>
        {d ? (
          <div>
            <div className="mb-4 flex flex-wrap gap-2">
              <Badge status={d.algorithm} />
              <Badge status={d.data_distribution} />
              <span className="badge">
                <Users size={11} /> {d.clients} clients
              </span>
              <span className="badge">
                <Timer size={11} /> {d.rounds} rounds
              </span>
            </div>
            {d.description && <p className="mb-4 text-sm text-slate-400">{d.description}</p>}
            <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
              <Stat label="Final Accuracy" value={d.results?.final_accuracy != null ? pct(d.results.final_accuracy) : "—"} tone="text-mint" />
              <Stat label="Communication" value={d.results?.communication_bytes != null ? bytes(d.results.communication_bytes) : "—"} />
              <Stat label="Elapsed" value={d.results?.elapsed_ms != null ? `${(d.results.elapsed_ms / 1000).toFixed(1)}s` : "—"} />
              <Stat label="Failures" value={pct(d.node_failure_rate)} />
            </div>
            <Card title="Accuracy per Round" pad={false}>
              {d.results?.accuracy_curve?.length ? (
                <div className="p-3">
                  <CurveChart
                    data={(d.results.accuracy_curve as any[]).map((r) => ({ round: `R${r.round}`, accuracy: r.accuracy ?? 0 }))}
                    xKey="round"
                    lines={[{ key: "accuracy", color: COLORS[d.algorithm] ?? "#22d3ee" }]}
                    height={240}
                  />
                </div>
              ) : (
                <Empty title="No curve stored" />
              )}
            </Card>
          </div>
        ) : (
          <Empty title="Loading…" />
        )}
      </Modal>
    </div>
  );
}

/* ------------------------------------------------ sub-components */

function LatestResult({ data }: { data: { id: number; final_accuracy: number; rounds: any[]; communication_bytes: number; elapsed_ms: number } }) {
  const curve = (data.rounds ?? []).map((r: any) => ({ round: `R${r.round}`, accuracy: r.accuracy ?? 0 }));
  const participations = (data.rounds ?? []).map((r: any) => ({ round: `R${r.round}`, participated: r.participated_count ?? 0 }));
  return (
    <div>
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Final Accuracy" value={pct(data.final_accuracy)} tone="text-mint" />
        <Stat label="Communication" value={bytes(data.communication_bytes)} />
        <Stat label="Elapsed" value={`${(data.elapsed_ms / 1000).toFixed(1)}s`} />
        <Stat label="Rounds" value={data.rounds?.length ?? 0} />
      </div>
      {curve.length ? (
        <Card title="Accuracy per Round" pad={false}>
          <div className="p-3">
            <CurveChart data={curve} xKey="round" lines={[{ key: "accuracy", color: "#22d3ee" }]} height={240} />
          </div>
        </Card>
      ) : (
        <Empty title="No curve returned" />
      )}
      {participations.length > 1 && (
        <Card className="mt-4" title="Client Participation per Round" pad={false}>
          <div className="p-3">
            <BarsChart data={participations} xKey="round" bars={[{ key: "participated", color: "#a78bfa", name: "clients" }]} height={180} />
          </div>
        </Card>
      )}
    </div>
  );
}

function buildCurve(results: Record<string, any>) {
  const first = Object.values(results)[0];
  const n = first?.accuracy_curve?.length ?? 0;
  const out: Record<string, unknown>[] = [];
  for (let i = 0; i < n; i++) {
    const row: Record<string, unknown> = { round: `R${i + 1}` };
    for (const a of ["fedavg", "fedprox", "fedadam"]) {
      const pts = results[a]?.accuracy_curve;
      if (pts && pts[i]) row[a] = pts[i].accuracy;
    }
    out.push(row);
  }
  return out;
}

function LearnSection() {
  const cards = [
    {
      icon: <ShieldCheck size={20} />,
      title: "Secure Aggregation",
      body: "Each client masks its weight delta with a pair-wise secret shared with every other client. The server sums the masked deltas; the masks cancel exactly, so the aggregate is the true sum — while individual updates stay hidden even from the server.",
    },
    {
      icon: <Scale size={20} />,
      title: "FedAvg vs FedProx vs FedAdam",
      body: "FedAvg weights each delta by sample count. FedProx adds a proximal penalty keeping local models close to the global one — ideal for non-IID drift. FedAdam runs Adam on the server, giving adaptive steps and faster convergence on hard distributions.",
    },
    {
      icon: <Users size={20} />,
      title: "Client Selection & Failures",
      body: "Each round selects a random fraction of online nodes. Stragglers and failures are tolerated: the server simply aggregates whatever deltas arrive within the round window — try raising the fail rate in an experiment to see resilience degrade gracefully.",
    },
    {
      icon: <Timer size={20} />,
      title: "Why Non-IID is Hard",
      body: "With IID data, every client's gradient points the same direction. With pathological data, clients hold disjoint classes and their deltas can conflict — this is the core research challenge that algorithms like FedProx, FedNova and SCAFFOLD attack.",
    },
  ];
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {cards.map((c) => (
        <Card key={c.title}>
          <div className="mb-2.5 flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand/25 to-brand-violet/25 text-brand">
            {c.icon}
          </div>
          <h4 className="text-sm font-semibold text-slate-100">{c.title}</h4>
          <p className="mt-1.5 text-[13px] leading-relaxed text-slate-400">{c.body}</p>
        </Card>
      ))}
    </div>
  );
}
