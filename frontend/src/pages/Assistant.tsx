import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Send, Sparkles } from "lucide-react";
import { assistantApi, aiApi } from "../lib/api";
import { useAuth } from "../auth";
import { Button, Card, PageHead } from "../ui";

const SUGGESTIONS = [
  "Show the current federated round",
  "Compare model versions",
  "Explain model accuracy",
  "Which client contributes the most?",
  "Explain communication failures",
  "Recommend hyperparameter improvements",
  "Summarize the latest training",
  "How does secure aggregation protect privacy?",
];

interface Msg {
  role: "user" | "assistant";
  content: string;
  meta?: string;
}

export default function Assistant() {
  const { can } = useAuth();
  const [messages, setMessages] = useState<Msg[]>([
    { role: "assistant", content: "Hello! I'm your federated AI copilot. I can answer questions about rounds, models, clients, failures and tuning — backed by live platform data.", meta: "rule-based" },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [provider, setProvider] = useState<number>(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: providers } = useQuery({ queryKey: ["ai-providers-avail"], queryFn: aiApi.availableProviders });

  const ask = async (question?: string) => {
    const q = question ?? input;
    if (!q.trim() || busy) return;
    setMessages((m) => [...m, { role: "user", content: q }]);
    setInput("");
    setBusy(true);
    try {
      const res = await assistantApi.ask(q, provider || undefined);
      setMessages((m) => [...m, { role: "assistant", content: res.content as string, meta: `${res.status}${res.error ? ` · ${String(res.error).slice(0, 60)}` : ""}` }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: `I couldn't reach the platform: ${e instanceof Error ? e.message : "unknown error"}` }]);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  return (
    <div className="flex h-full flex-col">
      <PageHead
        title="AI Assistant"
        desc="Enterprise copilot for the federated platform. Uses your configured AI provider, or the built-in rule engine when no key is set."
        actions={
          can("ai:manage") ? (
            <select className="input w-64" value={provider} onChange={(e) => setProvider(Number(e.target.value))}>
              <option value={0}>Built-in rule engine</option>
              {(providers ?? []).map((p) => (
                <option key={p.id as number} value={p.id as number}>{p.name as string}</option>
              ))}
            </select>
          ) : undefined
        }
      />

      <Card className="flex min-h-0 flex-1 flex-col">
        <div className="flex-1 space-y-3 overflow-y-auto p-1">
          {messages.map((m, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${m.role === "user" ? "bg-gradient-to-r from-brand to-brand-deep text-ink-950" : "border border-white/10 bg-white/[0.04] text-slate-200"}`}>
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{m.content}</p>
                {m.meta && <p className="mt-1.5 text-[10px] uppercase tracking-wide text-slate-500">{m.meta}</p>}
              </div>
            </motion.div>
          ))}
          {busy && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="flex gap-1">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand" style={{ animationDelay: "0ms" }} />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand" style={{ animationDelay: "120ms" }} />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand" style={{ animationDelay: "240ms" }} />
              </span>
              Thinking…
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="mt-3 border-t border-white/5 pt-3">
          <div className="mb-2 flex flex-wrap gap-1.5">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => ask(s)} className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] text-slate-400 transition hover:border-brand/40 hover:text-brand">
                <Sparkles size={10} /> {s}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              className="input flex-1"
              placeholder="Ask about rounds, models, clients, failures, tuning…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask()}
            />
            <Button variant="primary" disabled={busy || !input.trim()} onClick={() => ask()}>
              <Send size={14} />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
