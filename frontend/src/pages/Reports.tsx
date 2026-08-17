import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Download, FileText } from "lucide-react";
import { reportApi } from "../lib/api";
import { Button, Card, Empty, PageHead, useToasts } from "../ui";

const REPORT_META: Record<string, { title: string; icon: string; desc: string }> = {
  executive: { title: "Executive Summary", icon: "🏢", desc: "KPIs and narrative for leadership" },
  technical: { title: "Technical Report", icon: "⚙️", desc: "Algorithms, rounds, communication and latency" },
  compliance: { title: "Compliance Report", icon: "📜", desc: "GDPR / HIPAA / ISO alignment and audit posture" },
  privacy: { title: "Privacy Report", icon: "🛡️", desc: "Budget accounting, masking and encryption posture" },
  audit: { title: "Audit Report", icon: "🔎", desc: "Recent immutable audit events with chain hashes" },
};

export default function Reports() {
  const { push, ui } = useToasts();
  const [selected, setSelected] = useState<string | null>(null);
  const { data: result, isLoading, refetch } = useQuery({
    queryKey: ["report", selected],
    queryFn: () => reportApi.generate(selected!),
    enabled: selected != null,
  });

  const download = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `federated-ai-${selected}-report.json`;
    a.click();
    URL.revokeObjectURL(url);
    push("success", "Report downloaded");
  };

  const data = result?.data ?? {};
  const entries = Object.entries(data).filter(([k]) => !["report_type", "generated_at", "generated_by", "period"].includes(k));

  return (
    <div>
      <PageHead
        title="Reports"
        desc="Generate executive, technical, compliance, privacy and audit reports from live platform data."
      />
      {ui}

      <div className="mb-5 grid gap-3 md:grid-cols-3 xl:grid-cols-5">
        {Object.entries(REPORT_META).map(([key, m]) => (
          <button
            key={key}
            onClick={() => setSelected(key)}
            className={`rounded-xl border p-4 text-left transition ${selected === key ? "border-brand/50 bg-brand/10 shadow-glow" : "border-white/10 bg-ink-850 hover:border-white/25"}`}
          >
            <div className="mb-2 text-2xl">{m.icon}</div>
            <p className={`text-sm font-semibold ${selected === key ? "text-brand" : "text-slate-200"}`}>{m.title}</p>
            <p className="mt-1 text-[11px] leading-snug text-slate-500">{m.desc}</p>
          </button>
        ))}
      </div>

      {selected ? (
        <Card
          title={`${REPORT_META[selected].title} · ${selected}`}
          subtitle={`Generated ${String(data.generated_at ?? "").slice(0, 19).replace("T", " ")} by ${String(data.generated_by ?? "")}`}
          actions={
            <>
              <Button size="sm" onClick={() => refetch()}><FileText size={13} /> Regenerate</Button>
              <Button size="sm" variant="primary" onClick={download}><Download size={13} /> Download JSON</Button>
            </>
          }
        >
          {isLoading ? (
            <div className="space-y-2">{Array.from({ length: 8 }).map((_, i) => <div key={i} className="h-9 animate-pulse rounded-lg bg-white/5" />)}</div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-white/5">
              {entries.map(([k, v]) => (
                <div key={k} className="flex border-b border-white/5 last:border-0">
                  <div className="w-1/3 shrink-0 border-r border-white/5 bg-white/[0.02] px-3.5 py-2.5 font-mono text-[11px] uppercase tracking-wide text-slate-500">
                    {k.replace(/_/g, " ")}
                  </div>
                  <div className="min-w-0 flex-1 px-3.5 py-2.5 text-sm text-slate-300">
                    {typeof v === "object" ? (
                      <pre className="max-h-40 overflow-auto font-mono text-[11px] text-slate-400">{JSON.stringify(v, null, 1)}</pre>
                    ) : (
                      String(v)
                    )}
                  </div>
                </div>
              ))}
              {!entries.length && <Empty title="No data" />}
            </div>
          )}
        </Card>
      ) : (
        <Card><Empty title="Select a report type" sub="Reports are assembled live from current platform metrics and audit state." /></Card>
      )}
    </div>
  );
}
