import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Radio, Wifi, Zap } from "lucide-react";
import { monitorApi } from "../lib/api";
import { useRealtime } from "../lib/ws";
import { Badge, Card, Empty, PageHead, Stat } from "../ui";
import { bytes, timeAgo } from "../lib/format";

export default function Monitor() {
  const qc = useQueryClient();
  const [live, setLive] = useState<Record<string, unknown>>({});
  const [feed, setFeed] = useState<{ event: string; data: Record<string, unknown>; ts: number }[]>([]);

  const { data, refetch } = useQuery({ queryKey: ["monitor"], queryFn: monitorApi.overview, refetchInterval: 4000 });
  const { data: timeline } = useQuery({ queryKey: ["monitor-timeline"], queryFn: monitorApi.timeline, refetchInterval: 6000 });

  const { connected } = useRealtime((ev) => {
    if (ev.event === "round.complete" || ev.event === "node.training" || ev.event === "job.completed" || ev.event === "monitor.tick") {
      qc.invalidateQueries({ queryKey: ["monitor"] });
    }
    setFeed((f) => [{ event: ev.event, data: ev.data, ts: Date.now() }, ...f].slice(0, 40));
  });

  useEffect(() => {
    const iv = setInterval(() => refetch(), 5000);
    return () => clearInterval(iv);
  }, [refetch]);

  const o = (data ?? live) as Record<string, unknown>;
  const nodes = (o.node_sync as { id: number; name: string; status: string; latency_ms: number; bandwidth_mbps: number; trust_score: number; last_heartbeat: string | null; device_type: string; mtls: boolean }[]) ?? [];
  const rounds = (o.rounds as { id: number; round: number; status: string; accuracy: number | null; participated: number }[]) ?? [];
  const events = ((timeline?.events as Record<string, unknown>[]) ?? []).slice(0, 10);

  return (
    <div>
      <PageHead
        title="Communication Monitor"
        desc="Realtime federation telemetry: node health, synchronization, bandwidth, latency and round completion."
        actions={
          <span className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium ${connected ? "border-mint/25 bg-mint/10 text-mint" : "border-warn/25 bg-warn/10 text-warn"}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${connected ? "animate-pulse bg-mint" : "bg-warn"}`} />
            {connected ? "WebSocket live" : "Polling mode"}
          </span>
        }
      />

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <Stat label="Online" value={o.nodes_online ?? 0} tone="text-mint" />
        <Stat label="Total" value={o.nodes_total ?? 0} />
        <Stat label="Degraded" value={o.nodes_degraded ?? 0} tone="text-warn" />
        <Stat label="Offline" value={o.nodes_offline ?? 0} tone="text-danger" />
        <Stat label="Active Jobs" value={o.active_jobs ?? 0} tone="text-brand" />
        <Stat label="Rounds Done" value={o.rounds_completed ?? 0} />
        <Stat label="Avg Latency" value={`${o.avg_latency_ms ?? 0} ms`} sub="realtime" icon={<Zap size={15} />} />
        <Stat label="Bandwidth" value={`${Number(o.total_bandwidth_mbps ?? 0).toFixed(0)} Mbps`} sub="aggregate" icon={<Wifi size={15} />} />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" title="Node Synchronization" subtitle="Live node grid — heartbeats stream every 3 seconds">
          {!nodes.length ? (
            <Empty title="No nodes connected" icon={<Radio size={26} />} />
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {nodes.map((n) => (
                <div key={n.id} className={`rounded-xl border p-3 transition ${n.status === "online" ? "border-mint/15 bg-mint/[0.04]" : n.status === "degraded" ? "border-warn/15 bg-warn/[0.04]" : "border-danger/15 bg-danger/[0.04]"}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`h-2 w-2 rounded-full ${n.status === "online" ? "animate-pulse bg-mint" : n.status === "degraded" ? "bg-warn" : "bg-danger"}`} />
                      <p className="text-sm font-semibold text-slate-200">{n.name}</p>
                    </div>
                    <Badge status={n.status} />
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-1 text-center">
                    <div className="rounded-md bg-white/5 p-1.5">
                      <p className="font-mono text-xs text-slate-200">{n.latency_ms} ms</p>
                      <p className="text-[9px] uppercase text-slate-600">latency</p>
                    </div>
                    <div className="rounded-md bg-white/5 p-1.5">
                      <p className="font-mono text-xs text-slate-200">{n.bandwidth_mbps} Mbps</p>
                      <p className="text-[9px] uppercase text-slate-600">bandwidth</p>
                    </div>
                    <div className="rounded-md bg-white/5 p-1.5">
                      <p className="font-mono text-xs text-slate-200">{(n.trust_score * 100).toFixed(0)}%</p>
                      <p className="text-[9px] uppercase text-slate-600">trust</p>
                    </div>
                  </div>
                  <p className="mt-1.5 text-[10px] text-slate-600">{n.device_type} · {n.mtls ? "mTLS ✓" : "mTLS ✗"} · {timeAgo(n.last_heartbeat)}</p>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Round Completion Stream" subtitle="Latest aggregation events">
          {feed.length || rounds.length ? (
            <div className="max-h-[420px] space-y-1.5 overflow-y-auto pr-1">
              {feed.map((f, i) => (
                <div key={i} className="flex items-center gap-2.5 rounded-lg border border-white/5 bg-white/[0.02] px-2.5 py-2">
                  <Activity size={13} className="shrink-0 text-brand" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-mono text-[11px] text-slate-300">{f.event}</p>
                    <p className="truncate text-[10px] text-slate-600">{JSON.stringify(f.data).slice(0, 60)}</p>
                  </div>
                  <span className="shrink-0 text-[10px] text-slate-600">{new Date(f.ts).toLocaleTimeString()}</span>
                </div>
              ))}
              {!feed.length &&
                rounds.slice().reverse().map((r) => (
                  <div key={r.id} className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-2.5 py-2">
                    <span className="font-mono text-xs text-slate-300">Round {r.round}</span>
                    <span className="text-[11px] text-slate-500">{r.participated} clients</span>
                    <span className="font-mono text-[11px] text-mint">{(r.accuracy ?? 0).toFixed(3)}</span>
                  </div>
                ))}
            </div>
          ) : (
            <Empty title="Waiting for rounds" sub="Round events stream here in realtime." />
          )}
        </Card>
      </div>

      <Card className="mt-4" title="Node Events & Failures" subtitle="Recent events from the last 24 hours">
        {events.length ? (
          <div className="divide-y divide-white/5">
            {events.map((e) => (
              <div key={e.id as number} className="flex items-center gap-3 py-2.5">
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${(e.severity as string) === "warning" ? "bg-warn" : "bg-brand"}`} />
                <span className="w-28 shrink-0 font-mono text-[11px] text-slate-500">{e.event_type as string}</span>
                <p className="flex-1 truncate text-sm text-slate-300">{e.message as string}</p>
                <span className="text-[11px] text-slate-600">{timeAgo(e.created_at as string)}</span>
              </div>
            ))}
          </div>
        ) : (
          <Empty title="No events" sub="Events appear here as the federation runs." />
        )}
      </Card>
    </div>
  );
}
