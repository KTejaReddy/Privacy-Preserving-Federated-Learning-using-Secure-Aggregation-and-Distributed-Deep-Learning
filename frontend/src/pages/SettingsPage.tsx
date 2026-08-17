import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { KeyRound, User } from "lucide-react";
import { settingsApi } from "../lib/api";
import { useAuth } from "../auth";
import { Button, Card, Field, PageHead, Tabs, useToasts } from "../ui";

export default function SettingsPage() {
  const { user } = useAuth();
  const { push, ui } = useToasts();
  const [tab, setTab] = useState("profile");
  const [profile, setProfile] = useState({ full_name: user?.full_name ?? "", title: user?.title ?? "" });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });

  const { data } = useQuery({ queryKey: ["profile"], queryFn: settingsApi.profile });

  const saveProfile = useMutation({
    mutationFn: () => settingsApi.updateProfile(profile),
    onSuccess: () => push("success", "Profile updated"),
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });
  const changePw = useMutation({
    mutationFn: () => settingsApi.changePassword(pw.current_password, pw.new_password),
    onSuccess: () => {
      push("success", "Password changed");
      setPw({ current_password: "", new_password: "" });
    },
    onError: (e) => push("error", e instanceof Error ? e.message : "Failed"),
  });

  const p = data ?? user;
  const joined = p?.created_at;

  return (
    <div>
      <PageHead title="Settings" desc="Profile, security and platform preferences." />
      {ui}
      <div className="mb-4">
        <Tabs tabs={[{ key: "profile", label: "Profile" }, { key: "security", label: "Security" }]} value={tab} onChange={setTab} />
      </div>

      {tab === "profile" ? (
        <Card className="max-w-xl" title="Profile">
          <div className="mb-5 flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-brand to-brand-violet text-xl font-bold text-ink-950">
              {p?.full_name?.slice(0, 2).toUpperCase() ?? "—"}
            </div>
            <div>
              <p className="text-lg font-semibold text-white">{p?.full_name}</p>
              <p className="text-sm text-slate-500">{p?.email} · {p?.title || "No title"}</p>
              {joined && <p className="text-[11px] text-slate-600">Member since {new Date(joined).toLocaleDateString()}</p>}
            </div>
          </div>
          <div className="space-y-3">
            <Field label="Full name"><input className="input" value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} /></Field>
            <Field label="Title"><input className="input" value={profile.title} onChange={(e) => setProfile({ ...profile, title: e.target.value })} /></Field>
            <div className="flex justify-end">
              <Button variant="primary" disabled={saveProfile.isPending} onClick={() => saveProfile.mutate()}>
                <User size={14} /> Save profile
              </Button>
            </div>
          </div>
        </Card>
      ) : (
        <Card className="max-w-xl" title="Change Password">
          <div className="space-y-3">
            <Field label="Current password"><input type="password" className="input" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
            <Field label="New password" hint="At least 8 characters"><input type="password" className="input" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
            <div className="flex justify-end">
              <Button variant="primary" disabled={changePw.isPending || !pw.current_password || pw.new_password.length < 8} onClick={() => changePw.mutate()}>
                <KeyRound size={14} /> Update password
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
