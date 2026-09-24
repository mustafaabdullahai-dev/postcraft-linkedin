import type { PostRecord } from "../types";

interface Props {
  items: PostRecord[];
  busyLabel?: string;
  onPick: (rec: PostRecord) => void;
  onClose: () => void;
}

function Preview({ rec }: { rec: PostRecord }) {
  const body = rec.final_post ?? rec.generated_post;
  const text = body.slice(0, 300);
  const words = body.trim().split(/\s+/).filter(Boolean).length;
  return (
    <div className="min-w-0 space-y-2 text-left">
      <p className="truncate text-xs font-semibold" style={{ color: "var(--ink)" }}>
        {rec.user_query || rec.topic || rec.record_id}
      </p>
      <p className="line-clamp-4 whitespace-pre-line text-[11px] leading-relaxed" style={{ color: "var(--muted)" }}>
        {text}
        {body.length > 300 ? "…" : ""}
      </p>
      <p className="text-[10px]" style={{ color: "var(--faint)" }}>
        {words} words · {rec.post_type}
      </p>
    </div>
  );
}

export default function VariationPicker({ items, onPick, onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Choose your favourite draft"
    >
      <div
        className="w-full max-w-2xl rounded-2xl border p-5"
        style={{ background: "var(--surface)", borderColor: "var(--line)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-bold" style={{ color: "var(--ink)" }}>
              3 drafts ready — pick your favourite
            </h2>
            <p className="hint">The others stay in History so nothing is lost. You can delete them anytime.</p>
          </div>
          <button type="button" onClick={onClose} className="btn-ghost !px-2 !py-1 text-sm" aria-label="Close">
            ✕
          </button>
        </div>

        <ul className="grid gap-3 sm:grid-cols-3">
          {items.map((rec, i) => (
            <li
              key={rec.record_id}
              className={`flex flex-col justify-between gap-3 rounded-xl border p-3 ${rec.record_status === "FAILED" ? "opacity-60" : ""}`}
              style={{ borderColor: "var(--line-2)", background: "var(--surface-1)" }}
            >
              <div className={rec.record_status === "FAILED" ? "grayscale" : ""}>
                <Preview rec={rec} />
              </div>
              <button
                type="button"
                disabled={rec.record_status === "FAILED"}
                onClick={() => onPick(rec)}
                className="btn-primary py-2 text-xs"
              >
                {rec.record_status === "FAILED" ? "Generation failed" : `Use draft ${["one", "two", "three"][i] ?? i + 1}`}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}