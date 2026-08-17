import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, UserCog } from "lucide-react";
import { adminApi } from "../lib/api";
import { Badge, Button, Card, Field, Modal, PageHead, Tabs, useToasts } from "../ui";
import { timeAgo } from "../lib/format";

export default function Admin() {
  const qc = useQueryClient();
  const { push, ui } = useToasts();
  const [tab, setTab] = useState("users");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Record<string, string | number | boolean>>({});

  const { data: users } = useQuery({ queryKey: ["admin-users"], queryFn: adminApi.users });
  const { data: roles } = useQuery({ queryKey: ["admin-roles"], queryFn: adminApi.roles });
  const { data: flags } = useQuery({ queryKey: ["admin-flags"], queryFn: adminApi.flags });
  const { data: system } = useQuery({ queryKey: ["admin-system"], queryFn: adminApi.system });

  const createUser = useMutation({
    mutationFn: () => adminApi.createUser(form),
    onSuccess: () => {
      push("success", "User created");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const removeUser = useMutation({
    mutationFn: (id: number) => adminApi.removeUser(id),
    onSuccess: () => {
      push("success", "User removed");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const toggleFlag = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) => adminApi.updateFlag(key, !enabled),
    onSuccess: () => {
      push("success", "Feature flag updated");
      qc.invalidateQueries({ queryKey: ["admin-flags"] });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div>
      <PageHead
        title="Admin Panel"
        desc="Platform administration: users, roles, feature flags and system status."
        actions={
          <Button variant="primary" onClick={() => { setForm({ email: "", password: "Admin@12345", full_name: "", role: "ml_engineer", title: "" }); setOpen(true); }}>
            <Plus size={15} /> Create User
          </Button>
        }
      />
      {ui}

      <div className="mb-4">
        <Tabs tabs={[{ key: "users", label: "Users & Roles" }, { key: "flags", label: "Feature Flags" }, { key: "system", label: "System" }]} value={tab} onChange={setTab} />
      </div>

      {tab === "users" && (
        <Card title={`${users?.length ?? 0} platform users`}>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="th">User</th>
                  <th className="th">Role</th>
                  <th className="th">Title</th>
                  <th className="th">Status</th>
                  <th className="th">Last Login</th>
                  <th className="th">Created</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {(users ?? []).map((u) => (
                  <tr key={u.id} className="row-hover">
                    <td className="td">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand/25 to-brand-violet/25 text-xs font-bold text-brand">
                          {u.full_name.slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-slate-200">{u.full_name}</p>
                          <p className="text-[11px] text-slate-500">{u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="td">
                      <span className="badge border border-brand/20 bg-brand/10 text-brand">{u.role}</span>
                    </td>
                    <td className="td text-slate-400">{u.title || "—"}</td>
                    <td className="td"><Badge status={u.is_active ? "active" : "offline"} /></td>
                    <td className="td text-slate-500">{u.last_login ? timeAgo(u.last_login) : "never"}</td>
                    <td className="td text-slate-500">{timeAgo(u.created_at)}</td>
                    <td className="td">
                      <button className="rounded p-1.5 text-slate-500 hover:bg-white/10 hover:text-danger" onClick={() => removeUser.mutate(u.id)}>
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {tab === "flags" && (
        <Card title="Feature Flags" subtitle="Runtime toggles — changes are audited">
          <div className="divide-y divide-white/5">
            {(flags ?? []).map((f) => (
              <div key={f.key as string} className="flex items-center justify-between py-3">
                <div>
                  <p className="font-mono text-sm font-medium text-slate-200">{f.key as string}</p>
                  <p className="text-[11px] text-slate-500">{f.description as string}</p>
                </div>
                <button
                  onClick={() => toggleFlag.mutate({ key: f.key as string, enabled: f.enabled as boolean })}
                  className={`relative h-6 w-11 rounded-full transition ${f.enabled ? "bg-brand/70" : "bg-white/10"}`}
                >
                  <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${f.enabled ? "left-[22px]" : "left-0.5"}`} />
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {tab === "system" && system && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Object.entries(system as Record<string, unknown>).map(([k, v]) => (
            <div key={k} className="panel panel-hover p-4">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{k.replace(/_/g, " ")}</p>
              <p className="mt-1 truncate font-mono text-sm text-slate-200">{String(v)}</p>
            </div>
          ))}
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Create Platform User">
        <div className="space-y-3">
          <Field label="Full name"><input className="input" value={form.full_name as string} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
          <Field label="Email"><input className="input" value={form.email as string} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Role">
            <select className="input" value={form.role as string} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {(roles ?? []).map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}
            </select>
          </Field>
          <Field label="Title"><input className="input" value={form.title as string} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
          <Field label="Password"><input className="input" value={form.password as string} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="primary" disabled={!form.email || createUser.isPending} onClick={() => createUser.mutate()}>
              <UserCog size={14} /> {createUser.isPending ? "Creating…" : "Create user"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
