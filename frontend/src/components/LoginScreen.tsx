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
    <>
      {/* ── dark shaded outline (vignette + frame) around the page ── */}
    <div aria-hidden="true" className="pointer-events-none fixed inset-0" style={{ zIndex: 40, border: "14px solid rgba(0, 0, 0, 0.82)" }} />
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0"
      style={{
        zIndex: 41,
        background:
          "radial-gradient(ellipse at center, transparent 58%, rgba(0, 0, 0, 0.35) 82%, rgba(0, 0, 0, 0.9) 100%)",
      }}
    />

    <div className="flex h-screen w-full flex-col items-center justify-center overflow-hidden px-5 py-5 sm:px-6 sm:py-10">
      <div className="grid w-full max-w-5xl gap-4 sm:gap-6 lg:grid-cols-2 lg:items-stretch">
        {/* ── brand panel ─────────────────────────────────────── */}
        <section
          className="rv flex flex-col gap-3 rounded-[1.75rem] border px-5 py-5 sm:gap-4 sm:px-6 sm:py-7 lg:px-10 lg:py-10"
          style={{
            borderColor: "var(--line)",
            backgroundColor: "var(--surface)",
            backgroundImage:
              "linear-gradient(135deg, var(--surface) 0%, color-mix(in srgb, var(--accent) 16%, var(--surface)) 55%, color-mix(in srgb, var(--accent-2) 13%, var(--surface)) 100%)",
          }}
        >
          <div className="flex items-center gap-3">
            <span className="relative inline-flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl">
              <span
                aria-hidden="true"
                className="absolute -inset-2 -z-10 rounded-2xl opacity-70"
                style={{
                  background:
                    "radial-gradient(circle, color-mix(in srgb, var(--accent) 42%, transparent) 0%, transparent 72%)",
                }}
              />
              <img src="/favicon.png" alt="" className="brand-logo h-14 w-14 rounded-2xl" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-base font-bold tracking-tight" style={{ color: "var(--ink)" }}>
                PostCraft
              </p>
              <p className="label mt-0.5">AI LinkedIn content agent</p>
            </div>
          </div>

          <h2 className="text-xl font-extrabold leading-tight tracking-tight sm:text-2xl" style={{ color: "var(--ink)" }}>
            Draft it. Refine it.
            <br />
            Post it — with AI.
          </h2>

          <p className="hint leading-relaxed hidden sm:block">
            Turn any topic into a LinkedIn-ready post, review it with AI editing help, and publish straight
            to your own feed — using your own account.
          </p>

          <ul className="hidden flex-col gap-2.5 sm:flex">
            {[
              ["✦", "Generate", "LinkedIn-optimized drafts in your language and voice."],
              ["✎", "Review", "Edit freely — links, hashtags, and inline AI suggestions."],
              ["🚀", "Publish", "Approve once, and it goes live on your LinkedIn profile."],
            ].map(([icon, title, desc]) => (
              <li
                key={title}
                className="flex items-start gap-2.5 rounded-xl px-3 py-2.5"
                style={{ background: "var(--surface-2)" }}
              >
                <span aria-hidden="true" className="w-6 shrink-0 text-center text-sm" style={{ color: "var(--accent)" }}>
                  {icon}
                </span>
                <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
                  <span className="font-bold" style={{ color: "var(--ink-soft)" }}>
                    {title}
                  </span>{" "}
                  — {desc}
                </p>
              </li>
            ))}
          </ul>

          <div className="hidden flex-wrap gap-1.5 sm:flex">
            {["AI-DRAFTED", "YOUR-OAUTH", "OPEN-SOURCE"].map((chip) => (
              <span
                key={chip}
                className="rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide"
                style={{ borderColor: "var(--line-2)", background: "var(--surface)", color: "var(--faint)" }}
              >
                {chip}
              </span>
            ))}
          </div>
        </section>

        {/* ── auth card ───────────────────────────────────────── */}
        <section className="card rv flex w-full flex-col items-center justify-center gap-4 p-5 text-center sm:gap-5 sm:p-8">
          <header>
            <h2 className="text-lg font-bold tracking-tight" style={{ color: "var(--ink)" }}>
              Sign in to PostCraft
            </h2>
            <p className="hint mt-1">Your AI assistant for LinkedIn content.</p>
          </header>

        <div className="flex w-full max-w-[17rem] flex-col gap-3">
            <button
              type="button"
              onClick={loginWithLinkedIn}
              disabled={busy !== null}
              className={`flex min-h-11 w-full items-center justify-center gap-2 rounded-xl px-4 py-3 font-semibold transition ${
                health?.linkedin_configured
                  ? "bg-[#0A66C2] text-white shadow-lg hover:bg-[#0855a6]"
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

            <button type="button" onClick={loginAsGuest} disabled={busy !== null} className="btn-ghost min-h-11 w-full py-3">
              {busy === "guest" ? "Starting…" : "Continue as guest (demo)"}
            </button>
          </div>

          <label className="flex w-full max-w-[17rem] cursor-pointer items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-2)] px-4 py-3">
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

          <p className="flex items-center justify-center gap-1.5 text-center text-xs text-[var(--faint)]">
            <span
              aria-hidden="true"
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{ background: health ? "var(--ok)" : "var(--bad)" }}
            />
            {health ? "Your AI assistant for LinkedIn content." : "backend not reachable — start uvicorn on :8001"}
          </p>

          {error && (
            <p className="w-full max-w-[17rem] rounded-lg border border-[var(--bad-soft)] bg-[var(--bad-soft)] px-3 py-2 text-center text-xs text-[var(--bad)]">
              {error}
            </p>
          )}
        </section>
      </div>

      <p className="mt-3 text-center text-xs text-[var(--faint)]">
        Created by{" "}
        <span className="font-medium text-[var(--ink-soft)]">Abdullah Mustafa</span>
        <span className="px-1.5 opacity-60" aria-hidden="true">
          •
        </span>
        <span className="font-medium text-[var(--ink-soft)]">GenAI Engineer</span>
      </p>
      </div>
    </>
  );
}