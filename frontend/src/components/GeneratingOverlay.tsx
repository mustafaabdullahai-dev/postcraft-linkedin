import type { ProgressSnapshot } from "../services/api";

const FALLBACK_STAGES = [
  { key: "brief", label: "Shaping your idea into a clear brief", done: false, active: true },
  { key: "copy", label: "Writing the post copy", done: false, active: false },
  { key: "extras", label: "Adding hashtags and the image brief", done: false, active: false },
  { key: "visual", label: "Generating the visual", done: false, active: false },
  { key: "quality", label: "Checking quality & the hook", done: false, active: false },
  { key: "review", label: "Preparing your review", done: false, active: false },
];

export default function GeneratingOverlay({
  snapshot,
  elapsedMs = 0,
}: {
  snapshot: ProgressSnapshot | null;
  elapsedMs?: number;
}) {
  // Until the first frame lands there is nothing truthful to show yet, so the
  // checklist stays neutral instead of ticking itself along on a timer.
  const stages = snapshot?.stages?.length ? snapshot.stages : FALLBACK_STAGES;
  const finished = stages.filter((s) => s.done).length;
  const seconds = Math.round(elapsedMs / 1000);
  const settled = stages.length > 0 && finished === stages.length;

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
          <img
            src="/favicon.png"
            alt=""
            className="h-9 w-9 rounded-xl"
            aria-hidden="true"
          />
        </div>

        <div>
          <p className="text-lg font-bold" style={{ color: "var(--ink)" }}>
            {settled ? "Finishing up…" : "Generating your post…"}
          </p>
          <p className="hint mt-1">
            {seconds > 0 ? `${seconds}s elapsed · ` : ""}
            {finished}/{stages.length} steps done — keep this tab open.
          </p>
        </div>

        <div
          className="h-1.5 w-full overflow-hidden rounded-full"
          style={{ background: "var(--line)" }}
        >
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${stages.length ? (finished / stages.length) * 100 : 4}%`,
              background: "var(--accent)",
            }}
          />
        </div>

        <ul className="w-full space-y-2 text-left">
          {stages.map((s, i) => (
            <li
              key={s.key}
              className={`flex items-center gap-2.5 rounded-lg border px-3 py-2 text-xs font-medium transition-all duration-300 ${
                s.active ? "border-[var(--accent-soft)] bg-[var(--surface-2)]" : s.done ? "" : "opacity-45"
              }`}
              style={{
                borderColor: s.active ? "var(--accent-soft)" : s.done ? "var(--line-2)" : "var(--line)",
                color: s.active ? "var(--ink)" : s.done ? "var(--muted)" : "var(--faint)",
              }}
            >
              <span
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
                style={{
                  background: s.done ? "var(--ok)" : s.active ? "var(--accent-soft)" : "var(--surface-2)",
                  color: s.done ? "#fff" : s.active ? "var(--accent)" : "var(--faint)",
                }}
              >
                {s.done ? "✓" : s.active ? "•" : i + 1}
              </span>
              {s.label}
              {s.active && <span className="ml-auto h-2 w-2 animate-pulse rounded-full bg-[var(--accent)]" />}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}