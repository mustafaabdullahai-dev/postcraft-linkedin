import { useEffect, useState } from "react";
import { guestLogin, linkedinLoginUrl } from "../services/auth";
import type { HealthInfo, User } from "../types";
import { api } from "../services/api";

interface Props {
  onAuthed: (user: User) => void;
}

export default function LoginScreen({ onAuthed }: Props) {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [busy, setBusy] = useState<"linkedin" | "guest" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [remember, setRemember] = useState(true);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  const loginWithLinkedIn = () => {
    if (!health?.linkedin_configured) {
      setError(
        "LinkedIn OAuth isn't configured yet. Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in backend/.env, or continue as guest.",
      );
      return;
    }
    setBusy("linkedin");
    window.location.href = linkedinLoginUrl(remember);
  };

  const loginAsGuest = async () => {
    setBusy("guest");
    setError(null);
    try {
      const user = await guestLogin("", remember);
      if (user) onAuthed(user);
      else setError("Could not start a guest session. Is the backend running?");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="card rv w-full max-w-md space-y-6 p-8">
        <div className="space-y-2 text-center">
          <img src="/favicon.png" alt="" className="mx-auto h-16 w-16 rounded-2xl" />
          <h1 className="text-xl font-bold text-[var(--ink)]">PostCraft</h1>
          <p className="label">AI LinkedIn content agent</p>
          <p className="hint">
            Sign in to generate, review, approve, and publish posts to your own LinkedIn.
          </p>
        </div>

        <div className="space-y-3">
          <button
            type="button"
            onClick={loginWithLinkedIn}
            disabled={busy !== null}
            className={`flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 font-semibold transition ${
              health?.linkedin_configured
                ? "bg-[#0A66C2] text-white hover:bg-[#0855a6]"
                : "cursor-not-allowed border border-[var(--line)] bg-[var(--surface-2)] text-[var(--faint)]"
            }`}
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current" aria-hidden="true">
              <path d="M4.98 3.5a2.49 2.49 0 1 1 0 4.98 2.49 2.49 0 0 1 0-4.98zM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05C20.4 8.65 21 11.1 21 14.2V21h-4v-6c0-1.43-.03-3.27-2-3.27-2 0-2.3 1.56-2.3 3.17V21H9z" />
            </svg>
            {health?.linkedin_configured ? "Sign in with LinkedIn" : "LinkedIn (not configured)"}
          </button>

          <div className="flex items-center gap-3 text-xs text-[var(--faint)]">
            <span className="h-px flex-1 bg-[var(--line-2)]" />
            or
            <span className="h-px flex-1 bg-[var(--line-2)]" />
          </div>

          <button type="button" onClick={loginAsGuest} disabled={busy !== null} className="btn-ghost w-full py-3">
            {busy === "guest" ? "Starting…" : "Continue as guest (demo)"}
          </button>
        </div>

        <label className="flex cursor-pointer items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-2)] px-4 py-3">
          <span className="text-xs font-medium text-[var(--ink-soft)]">
            Remember me
            <span className="mt-0.5 block text-[10px] leading-tight text-[var(--faint)]">
              Stay signed in after you close the browser
            </span>
          </span>
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="h-4 w-4 accent-[#2f6fed]"
          />
        </label>

        <p className="text-center text-xs text-[var(--faint)]">
          {health ? "Your AI assistant for LinkedIn content." : "backend not reachable — start uvicorn on :8001"}
        </p>

        {error && (
          <p className="rounded-lg border border-[var(--bad-soft)] bg-[var(--bad-soft)] px-3 py-2 text-center text-xs text-[var(--bad)]">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}