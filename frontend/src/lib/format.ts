import { formatDistanceToNow, format } from "date-fns";

export const pct = (v?: number | null, digits = 1) =>
  v == null ? "—" : `${(v * 100).toFixed(digits)}%`;

export const num = (v?: number | null, digits = 2) =>
  v == null ? "—" : v.toFixed(digits);

export const bytes = (b?: number | null) => {
  if (b == null) return "—";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(2)} MB`;
};

export const ms = (v?: number | null) => {
  if (v == null) return "—";
  if (v < 1000) return `${v} ms`;
  return `${(v / 1000).toFixed(1)} s`;
};

export const timeAgo = (d?: string | null) =>
  d ? formatDistanceToNow(new Date(d), { addSuffix: true }) : "—";

export const dateTime = (d?: string | null) =>
  d ? format(new Date(d), "MMM d, HH:mm:ss") : "—";

export const roundMs = (v?: number | null) => ms(v);

export const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

export function scoreColor(v: number): string {
  if (v >= 0.7) return "text-mint";
  if (v >= 0.45) return "text-warn";
  return "text-danger";
}

export function statusTone(status: string): string {
  const s = status.toLowerCase();
  if (["online", "completed", "active", "deployed", "approved", "verified", "ok", "healthy", "established", "low"].includes(s))
    return "bg-mint/10 text-mint border border-mint/20";
  if (["running", "training", "pending", "approved", "testing", "aggregating", "registered", "configured", "queued"].includes(s) || s.includes("train") || s.includes("aggregat"))
    return "bg-brand/10 text-brand border border-brand/20";
  if (["degraded", "warning", "draft", "paused", "pending_approval", "unknown", "fallback"].includes(s))
    return "bg-warn/10 text-warn border border-warn/20";
  if (["offline", "failed", "error", "cancelled", "rejected", "quarantined", "unreachable", "high", "critical"].includes(s))
    return "bg-danger/10 text-danger border border-danger/20";
  return "bg-white/5 text-slate-400 border border-white/10";
}

export function toneDot(status: string): string {
  const s = status.toLowerCase();
  if (["online", "completed", "active", "deployed", "approved", "verified", "ok"].includes(s)) return "bg-mint";
  if (["running", "training", "pending", "approved", "aggregating"].includes(s) || s.includes("train")) return "bg-brand";
  if (["degraded", "warning", "draft", "paused", "unknown"].includes(s)) return "bg-warn";
  if (["offline", "failed", "error", "cancelled", "rejected"].includes(s)) return "bg-danger";
  return "bg-slate-500";
}

export const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
