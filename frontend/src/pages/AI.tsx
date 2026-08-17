import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plug, Plus, Trash2, Zap } from "lucide-react";
import { aiApi } from "../lib/api";
import { useAuth } from "../auth";
import { Badge, Button, Card, Empty, Field, Modal, PageHead, Tabs, useToasts } from "../ui";
import { timeAgo } from "../lib/format";

export default function AI() {
  const { can, user } = useAuth();
  const isAdmin = can("ai:manage");
  const qc = useQueryClient();
  const { push, ui } = useToasts();
  const [tab, setTab] = useState("providers");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Record<string, unknown>>({});

  const { data: specs } = useQuery({ queryKey: ["ai-specs"], queryFn: aiApi.specs, enabled: isAdmin });
  const { data: providers } = useQuery({ queryKey: ["ai-providers"], queryFn: aiApi.providers, enabled: isAdmin });
  const { data: prompts } = useQuery({ queryKey: ["ai-prompts"], queryFn: aiApi.prompts });
  const { data: logs } = useQuery({ queryKey: ["ai-logs"], queryFn: aiApi.inferenceLogs, refetchInterval: 4000 });

  const createProvider = useMutation({
    mutationFn: () => aiApi.createProvider(form),
    onSuccess: () => {
      push("success", "Provider configured · API key encrypted with AES-256");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["ai-providers"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const test = useMutation({
    mutationFn: (id: number) => aiApi.testProvider(id),
    onSuccess: (r, id) => {
      if (r.ok) push("success", `Connected · ${r.message}`);
      else push("error", r.message);
      qc.invalidateQueries({ queryKey: ["ai-providers"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const removeProvider = useMutation({
    mutationFn: (id: number) => aiApi.removeProvider(id),
    onSuccess: () => {
      push("success", "Provider removed");
      qc.invalidateQueries({ queryKey: ["ai-providers"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const createPrompt = useMutation({
    mutationFn: () => aiApi.createPrompt(form),
    onSuccess: () => {
      push("success", "Prompt template saved");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["ai-prompts"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const removePrompt = useMutation({
    mutationFn: (id: number) => aiApi.removePrompt(id),
    onSuccess: () => {
      push("success", "Prompt deleted");
      qc.invalidateQueries({ queryKey: ["ai-prompts"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });

  const specList = (specs ?? []) as { provider_type: string; label: string; default_models: string[] }[];

  return (
    <div>
      <PageHead
        title="AI Integrations"
        desc="Bring-your-own-key enterprise AI gateway. Keys are AES-256 encrypted at rest and never exposed."
        actions={
          tab === "providers" && isAdmin ? (
            <Button variant="primary" onClick={() => { setForm({ provider_type: "openai", name: "", api_key: "", models: [], base_url: "" }); setOpen(true); }}>
              <Plus size={15} /> Configure Provider
            </Button>
          ) : tab === "prompts" ? (
            <Button variant="primary" onClick={() => { setForm({ name: "", system_prompt: "", user_prompt: "", variables: [], temperature: 0.3 }); setOpen(true); }}>
              <Plus size={15} /> New Template
            </Button>
          ) : undefined
        }
      />
      {ui}

      {!isAdmin && (
        <div className="mb-4 rounded-xl border border-warn/25 bg-warn/5 p-4 text-sm text-warn">
          🔐 Provider management is restricted to administrators. You can still use configured providers for chat and the assistant.
        </div>
      )}

      <div className="mb-4">
        <Tabs
          tabs={[
            { key: "providers", label: "Providers" },
            { key: "prompts", label: "Prompt Studio" },
            { key: "logs", label: "Inference Logs" },
          ]}
          value={tab}
          onChange={setTab}
        />
      </div>

      {tab === "providers" && (
        isAdmin ? (
          <div className="grid gap-4 md:grid-cols-2">
            {(providers ?? []).map((p) => (
              <Card key={p.id} title={p.name} subtitle={p.provider_type} className="relative">
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Endpoint</span>
                    <span className="font-mono text-xs text-slate-300">{p.base_url}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">API key</span>
                    <span className="flex items-center gap-1.5 font-mono text-xs text-slate-300">
                      <KeyRound size={12} className="text-mint" /> {p.key_mask || "not set"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Models</span>
                    <span className="text-xs text-slate-300">{p.models.slice(0, 2).join(", ") || "—"}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Status</span>
                    <Badge status={p.status} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Latency</span>
                    <span className="font-mono text-xs text-slate-300">{p.latency_ms ? `${p.latency_ms} ms` : "—"}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Configured</span>
                    <span className="text-xs text-slate-400">{timeAgo(p.created_at)}</span>
                  </div>
                </div>
                <div className="mt-4 flex gap-2">
                  <Button size="sm" variant="primary" disabled={test.isPending} onClick={() => test.mutate(p.id)}>
                    <Plug size={12} /> {test.isPending ? "Testing…" : "Test connection"}
                  </Button>
                  <Button size="sm" onClick={() => removeProvider.mutate(p.id)}>
                    <Trash2 size={12} /> Remove
                  </Button>
                </div>
              </Card>
            ))}
            {!providers?.length && <Card><Empty title="No providers configured" sub="Connect your own OpenAI, Claude, Gemini, Groq or other keys." /></Card>}
          </div>
        ) : (
          <Card><Empty title="Admin access required" sub="Ask an administrator to configure AI providers." /></Card>
        )
      )}

      {tab === "prompts" && (
        <Card title="Prompt Templates">
          {!prompts?.length ? (
            <Empty title="No templates yet" sub="Create reusable prompt templates for the assistant." />
          ) : (
            <div className="divide-y divide-white/5">
              {prompts.map((p) => (
                <div key={p.id as number} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-200">{p.name as string}</p>
                    <p className="truncate text-[11px] text-slate-500">{(p.system_prompt as string)?.slice(0, 80) || "—"}</p>
                  </div>
                  <button className="rounded p-1.5 text-slate-500 hover:bg-white/10 hover:text-danger" onClick={() => removePrompt.mutate(p.id as number)}>
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {tab === "logs" && (
        <Card title="Inference Logs">
          {!logs?.length ? (
            <Empty title="No inference calls yet" sub="Chat with a provider or use the assistant to populate logs." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="th">Provider</th>
                    <th className="th">Model</th>
                    <th className="th">Prompt</th>
                    <th className="th">Response</th>
                    <th className="th">Latency</th>
                    <th className="th">Tokens</th>
                    <th className="th">Status</th>
                    <th className="th">When</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {logs.map((l) => (
                    <tr key={l.id as number} className="row-hover">
                      <td className="td text-slate-300">{l.provider_name as string}</td>
                      <td className="td font-mono text-[11px] text-slate-400">{l.model as string}</td>
                      <td className="td max-w-48 truncate font-mono text-[11px] text-slate-500">{(l.prompt_preview as string)?.slice(0, 40)}</td>
                      <td className="td max-w-48 truncate font-mono text-[11px] text-slate-500">{(l.response_preview as string)?.slice(0, 40)}</td>
                      <td className="td font-mono text-slate-300">{l.latency_ms as number} ms</td>
                      <td className="td font-mono text-slate-400">{l.tokens as number}</td>
                      <td className="td"><Badge status={l.status as string} /></td>
                      <td className="td text-slate-500">{timeAgo(l.created_at as string)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={tab === "prompts" ? "New Prompt Template" : "Configure AI Provider"}>
        {tab === "providers" ? (
          <div className="space-y-3">
            <Field label="Provider">
              <select className="input" value={form.provider_type as string} onChange={(e) => setForm({ ...form, provider_type: e.target.value })}>
                {specList.map((s) => <option key={s.provider_type} value={s.provider_type}>{s.label}</option>)}
              </select>
            </Field>
            <Field label="Display name"><input className="input" value={form.name as string} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label="API key" hint="Encrypted at rest with AES-256-GCM. Never stored in plaintext.">
              <input type="password" className="input" value={form.api_key as string} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="sk-…" />
            </Field>
            <Field label="Base URL (optional)">
              <input className="input" value={form.base_url as string} onChange={(e) => setForm({ ...form, base_url: e.target.value })} />
            </Field>
            <Field label="Models (comma-separated)">
              <input className="input" value={(form.models as string[] ?? []).join(", ")} onChange={(e) => setForm({ ...form, models: e.target.value.split(",").map((m) => m.trim()).filter(Boolean) })} placeholder="gpt-4o, gpt-4o-mini" />
            </Field>
            <p className="flex items-center gap-1.5 rounded-lg border border-mint/20 bg-mint/5 px-3 py-2 text-[11px] text-mint">
              <Zap size={12} /> Keys are masked on display (sk****cdef) and only admins can manage providers.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <Button onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="primary" disabled={!form.name || createProvider.isPending} onClick={() => createProvider.mutate()}>
                {createProvider.isPending ? "Encrypting…" : "Save provider"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <Field label="Template name"><input className="input" value={form.name as string} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label="System prompt"><textarea className="input min-h-24" value={form.system_prompt as string} onChange={(e) => setForm({ ...form, system_prompt: e.target.value })} /></Field>
            <Field label="User prompt"><textarea className="input min-h-20" value={form.user_prompt as string} onChange={(e) => setForm({ ...form, user_prompt: e.target.value })} /></Field>
            <Field label="Variables (comma-separated)"><input className="input" value={(form.variables as string[] ?? []).join(", ")} onChange={(e) => setForm({ ...form, variables: e.target.value.split(",").map((v) => v.trim()).filter(Boolean) })} /></Field>
            <div className="flex justify-end gap-2 pt-2">
              <Button onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="primary" disabled={!form.name || createPrompt.isPending} onClick={() => createPrompt.mutate()}>
                Save template
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
