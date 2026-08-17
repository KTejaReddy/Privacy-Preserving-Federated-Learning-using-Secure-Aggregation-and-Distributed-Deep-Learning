import React, { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, AlertTriangle, CheckCircle2, Info } from "lucide-react";
import clsx from "clsx";
import { statusTone, toneDot, cap } from "./lib/format";

/* ---------------------------------------------------------------- Card */
export function Card({
  title,
  subtitle,
  actions,
  children,
  className,
  pad = true,
}: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  pad?: boolean;
}) {
  return (
    <div className={clsx("panel", className)}>
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 px-4 py-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
            {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={clsx(pad && "p-4")}>{children}</div>
    </div>
  );
}

/* ---------------------------------------------------------------- Stat */
export function Stat({
  label,
  value,
  sub,
  icon,
  tone = "text-slate-100",
  accent,
}: {
  label: string;
  value: unknown;
  sub?: React.ReactNode;
  icon?: React.ReactNode;
  tone?: string;
  accent?: string;
}) {
  return (
    <div className="panel panel-hover relative overflow-hidden p-4">
      <div
        className={clsx(
          "pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full opacity-10 blur-2xl",
          accent || "bg-brand"
        )}
      />
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
          <p className={clsx("mt-1.5 text-2xl font-bold tabular-nums", tone)}>{value as React.ReactNode}</p>
          {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
        </div>
        {icon && <div className="text-brand/80">{icon}</div>}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- Badge */
export function Badge({ status, children }: { status?: string; children?: React.ReactNode }) {
  const s = status ?? (typeof children === "string" ? children : "");
  return (
    <span className={clsx("badge", statusTone(s))}>
      <span className={clsx("h-1.5 w-1.5 rounded-full", toneDot(s))} />
      {cap(s.replace(/_/g, " "))}
    </span>
  );
}

/* ---------------------------------------------------------------- Buttons */
export function Button({
  variant = "ghost",
  size,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger";
  size?: "sm" | "md";
}) {
  return (
    <button
      className={clsx(
        variant === "primary" && "btn-primary",
        variant === "ghost" && "btn-ghost",
        variant === "danger" && "btn-danger",
        size === "sm" && "btn-sm",
        className
      )}
      {...props}
    />
  );
}

/* ---------------------------------------------------------------- Inputs */
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
      {hint && <p className="mt-1 text-[11px] text-slate-500">{hint}</p>}
    </div>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  children: React.ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.96, y: 12, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.96, y: 12, opacity: 0 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}
            className={clsx("panel max-h-[88vh] w-full overflow-y-auto", wide ? "max-w-3xl" : "max-w-lg")}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-white/5 px-5 py-3.5">
              <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
              <button onClick={onClose} className="rounded p-1 text-slate-500 hover:bg-white/10 hover:text-slate-200">
                <X size={16} />
              </button>
            </div>
            <div className="p-5">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ---------------------------------------------------------------- Tabs */
export function Tabs({
  tabs,
  value,
  onChange,
}: {
  tabs: { key: string; label: React.ReactNode }[];
  value: string;
  onChange: (k: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1 rounded-xl border border-white/5 bg-ink-900/60 p-1">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={clsx("tab", value === t.key ? "tab-active" : "tab-idle")}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- Progress */
export function Bar({ value, max = 1, tone }: { value: number; max?: number; tone?: string }) {
  const p = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
      <div
        className={clsx("h-full rounded-full transition-all", tone || "bg-gradient-to-r from-brand to-brand-violet")}
        style={{ width: `${p}%` }}
      />
    </div>
  );
}

/* ---------------------------------------------------------------- Empty */
export function Empty({ icon, title, sub }: { icon?: React.ReactNode; title: string; sub?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
      <div className="text-3xl opacity-60">{icon ?? "📭"}</div>
      <p className="text-sm font-medium text-slate-300">{title}</p>
      {sub && <p className="max-w-sm text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

/* ---------------------------------------------------------------- Toast */
type ToastKind = "success" | "error" | "info";
interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}
export function useToasts() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = (kind: ToastKind, message: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, message }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  };
  const ui = (
    <div className="pointer-events-none fixed right-4 top-4 z-[100] flex w-80 flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 40 }}
            className={clsx(
              "pointer-events-auto flex items-start gap-2.5 rounded-lg border px-3.5 py-3 text-sm shadow-lg backdrop-blur",
              t.kind === "success" && "border-mint/25 bg-mint/10 text-mint",
              t.kind === "error" && "border-danger/25 bg-danger/10 text-danger",
              t.kind === "info" && "border-brand/25 bg-brand/10 text-brand"
            )}
          >
            {t.kind === "success" && <CheckCircle2 size={16} className="mt-0.5 shrink-0" />}
            {t.kind === "error" && <AlertTriangle size={16} className="mt-0.5 shrink-0" />}
            {t.kind === "info" && <Info size={16} className="mt-0.5 shrink-0" />}
            <span>{t.message}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
  return { push, ui };
}

/* ---------------------------------------------------------------- helpers */
export function PageHead({
  title,
  desc,
  actions,
}: {
  title: string;
  desc?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-white">{title}</h1>
        {desc && <p className="mt-1 max-w-2xl text-sm text-slate-500">{desc}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={clsx(
        "animate-pulse rounded-md bg-white/5",
        className
      )}
    />
  );
}
