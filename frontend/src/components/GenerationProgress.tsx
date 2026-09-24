import type { Stage } from "../utils/format";

const STAGES: Stage[] = [
  { label: "Analyzing topic" },
  { label: "Planning content" },
  { label: "Writing draft" },
  { label: "Validating quality" },
  { label: "Generating image" },
  { label: "Finalizing post" },
];

export default function GenerationProgress({ elapsed }: { elapsed: number }) {
  const shown = Math.min(STAGES.length - 1, Math.floor(elapsed / 4));
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-[var(--accent)]">Generating with AI…</span>
        <span className="font-mono text-[var(--faint)]">{elapsed}s</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--line)]">
        <div
          className="h-full rounded-full bg-[var(--accent)] transition-all duration-700"
          style={{ width: `${Math.min(100, (elapsed / 24) * 100)}%` }}
        />
      </div>
      <div className="grid grid-cols-2 gap-1.5 text-xs sm:grid-cols-3">
        {STAGES.map((s, i) => (
          <div
            key={s.label}
            className={`tag justify-center !py-1.5 ${
              i < shown ? "tag--mint" : i === shown ? "tag--sky" : "tag--slate"
            }`}
          >
            {i < shown ? "✓ " : i === shown ? "● " : ""}
            {s.label}
          </div>
        ))}
      </div>
    </div>
  );
}