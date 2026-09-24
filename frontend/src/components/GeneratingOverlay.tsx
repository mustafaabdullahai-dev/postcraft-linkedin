import { useEffect, useState } from "react";

const STEPS = [
  "Shaping your idea into a clear brief",
  "Writing the post copy",
  "Checking quality & the hook",
  "Generating the visual",
  "Preparing your review",
];

export default function GeneratingOverlay() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    setStep(0);
    const id = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length)), 1400);
    return () => clearInterval(id);
  }, []);

  return (
    <div
      className="palette-overlay pointer-events-none fixed inset-0 z-[80] flex items-center justify-center p-4"
      style={{
        background: "color-mix(in srgb, var(--bg) 55%, transparent)",
        backdropFilter: "blur(6px)",
      }}
      role="status"
      aria-live="polite"
    >
      <div
        className="palette-pop pointer-events-auto flex w-full max-w-sm flex-col items-center gap-5 rounded-2xl border p-8 text-center"
        style={{
          background: "var(--surface)",
          borderColor: "var(--line)",
          boxShadow:
            "0 0 0 1px var(--bg), 0 0 0 2px var(--logo-ring), 0 0 0 5px color-mix(in srgb, var(--accent) 12%, transparent), 0 24px 60px -16px rgba(10,16,32,0.55)",
        }}
      >
        <div className="relative flex h-20 w-20 items-center justify-center">
          <div
            className="absolute inset-0 animate-spin rounded-full border-[3px]"
            style={{ borderColor: "var(--line-strong)", borderTopColor: "var(--accent)" }}
          />
          <div
            className="absolute inset-1.5 animate-spin rounded-full border-2"
            style={{ borderColor: "transparent", borderBottomColor: "var(--accent-2)", animationDirection: "reverse", animationDuration: "1.6s" }}
          />
          <span className="text-2xl">✨</span>
        </div>

        <div>
          <p className="text-lg font-bold" style={{ color: "var(--ink)" }}>
            Generating your post…
          </p>
          <p className="hint mt-1">Usually takes ~20 seconds — your draft lands here when it's ready.</p>
        </div>

        <ul className="w-full space-y-2 text-left">
          {STEPS.map((label, i) => {
            const done = i < step;
            const active = i === step;
            return (
              <li
                key={label}
                className={`flex items-center gap-2.5 rounded-lg border px-3 py-2 text-xs font-medium transition-all duration-300 ${
                  active ? "border-[var(--accent-soft)] bg-[var(--surface-2)]" : done ? "" : "opacity-45"
                }`}
                style={{
                  borderColor: active ? "var(--accent-soft)" : done ? "var(--line-2)" : "var(--line)",
                  color: active ? "var(--ink)" : done ? "var(--muted)" : "var(--faint)",
                }}
              >
                <span
                  className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
                  style={{
                    background: done ? "var(--ok)" : active ? "var(--accent-soft)" : "var(--surface-2)",
                    color: done ? "#fff" : active ? "var(--accent)" : "var(--faint)",
                  }}
                >
                  {done ? "✓" : active ? "•" : i + 1}
                </span>
                {label}
                {active && <span className="ml-auto h-2 w-2 animate-pulse rounded-full bg-[var(--accent)]" />}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}