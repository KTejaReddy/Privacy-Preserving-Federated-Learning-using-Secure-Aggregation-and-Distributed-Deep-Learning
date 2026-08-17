import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Lock, Mail, Zap, ShieldCheck, Network, BrainCircuit } from "lucide-react";
import { useAuth } from "../auth";
import { Button, Field } from "../ui";

const DEMO_ACCOUNTS = [
  { email: "admin@federated.ai", label: "Platform Admin", role: "Full platform control" },
  { email: "coordinator@federated.ai", label: "Federated Coordinator", role: "Rounds, orgs & approvals" },
  { email: "orgadmin@medicore.ai", label: "Organization Admin", role: "Local datasets & training" },
  { email: "ml@medicore.ai", label: "ML Engineer", role: "Models, eval & explainability" },
  { email: "research@nova.ai", label: "Research Scientist", role: "Federated Lab & experiments" },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: { pathname: string } } };
  const [email, setEmail] = useState("admin@federated.ai");
  const [password, setPassword] = useState("Admin@12345");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      navigate(location.state?.from?.pathname ?? "/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Brand panel */}
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden border-r border-white/5 bg-ink-900 p-10 lg:flex">
        <div className="absolute inset-0 opacity-40" style={{ backgroundImage: "radial-gradient(600px 300px at 20% 10%, rgba(34,211,238,0.14), transparent), radial-gradient(500px 300px at 80% 80%, rgba(167,139,250,0.12), transparent)" }} />
        <div className="relative flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-brand-violet shadow-glow">
            <Zap size={20} className="text-ink-950" />
          </div>
          <div>
            <p className="text-lg font-bold text-white">Federated AI Platform</p>
            <p className="text-xs text-slate-500">Privacy-Preserving Federated Learning</p>
          </div>
        </div>
        <div className="relative space-y-6">
          <h1 className="text-3xl font-bold leading-tight text-white">
            Secure Aggregation.
            <br />
            <span className="bg-gradient-to-r from-brand to-brand-violet bg-clip-text text-transparent">
              Distributed Deep Learning.
            </span>
            <br />
            Zero raw-data exposure.
          </h1>
          <div className="grid grid-cols-3 gap-3">
            {[
              { icon: <ShieldCheck size={18} />, t: "Bonawitz-style masked aggregation" },
              { icon: <Network size={18} />, t: "Multi-organization federated network" },
              { icon: <BrainCircuit size={18} />, t: "SHAP-based explainable AI center" },
            ].map((f) => (
              <div key={f.t} className="rounded-xl border border-white/5 bg-white/[0.03] p-3.5">
                <div className="mb-2 text-brand">{f.icon}</div>
                <p className="text-xs text-slate-400">{f.t}</p>
              </div>
            ))}
          </div>
        </div>
        <p className="relative text-xs text-slate-600">B.Tech Final Year Project · CS & Machine Learning</p>
      </div>

      {/* Form panel */}
      <div className="flex flex-1 items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md"
        >
          <div className="panel p-7">
            <h2 className="text-xl font-bold text-white">Sign in to the platform</h2>
            <p className="mt-1 text-sm text-slate-500">Enterprise federated learning control plane</p>
            <form onSubmit={submit} className="mt-6 space-y-4">
              <Field label="Email">
                <div className="relative">
                  <Mail size={15} className="absolute left-3 top-2.5 text-slate-500" />
                  <input className="input pl-9" value={email} onChange={(e) => setEmail(e.target.value)} />
                </div>
              </Field>
              <Field label="Password">
                <div className="relative">
                  <Lock size={15} className="absolute left-3 top-2.5 text-slate-500" />
                  <input type="password" className="input pl-9" value={password} onChange={(e) => setPassword(e.target.value)} />
                </div>
              </Field>
              {error && <p className="rounded-lg border border-danger/25 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</p>}
              <Button variant="primary" className="w-full py-2.5" disabled={busy}>
                {busy ? "Authenticating…" : "Sign in"}
              </Button>
            </form>
            <p className="mt-5 text-center text-[11px] text-slate-600">All passwords for demo accounts: <code className="rounded bg-white/10 px-1 py-0.5 font-mono">Admin@12345</code></p>
          </div>

          <div className="mt-4">
            <p className="mb-2 text-center text-[11px] font-semibold uppercase tracking-wider text-slate-600">
              Demo roles — click to sign in
            </p>
            <div className="grid gap-1.5">
              {DEMO_ACCOUNTS.map((a) => (
                <button
                  key={a.email}
                  onClick={() => {
                    setEmail(a.email);
                    setPassword("Admin@12345");
                    submit();
                  }}
                  className="group flex items-center justify-between rounded-lg border border-white/5 bg-ink-900/60 px-3.5 py-2.5 text-left transition hover:border-brand/30 hover:bg-brand/5"
                >
                  <div>
                    <p className="text-xs font-semibold text-slate-200 group-hover:text-brand">{a.label}</p>
                    <p className="text-[11px] text-slate-500">{a.role}</p>
                  </div>
                  <span className="font-mono text-[11px] text-slate-600 group-hover:text-brand">{a.email}</span>
                </button>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
