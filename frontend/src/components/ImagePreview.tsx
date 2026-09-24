import { useState } from "react";

interface Props {
  url: string;
  prompt: string;
  busy?: boolean;
  onRegenerate?: (prompt?: string) => void;
}

export default function ImagePreview({ url, prompt, busy, onRegenerate }: Props) {
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState(false);
  const [customPrompt, setCustomPrompt] = useState("");
  const isSvg = url.startsWith("data:image/svg") || url.endsWith(".svg");

  const applyCustom = () => {
    if (!customPrompt.trim() || busy) return;
    onRegenerate?.(customPrompt.trim());
  };

  return (
    <div className="space-y-2">
      <div className="overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--surface-2)]">
        {isSvg ? (
          <iframe
            title="generated image"
            src={url}
            className="h-56 w-full border-0"
            sandbox=""
            scrolling="no"
          />
        ) : (
          <img
            src={url}
            alt="AI generated for this post"
            className="h-56 w-full cursor-zoom-in object-cover transition hover:opacity-95"
            onClick={() => setOpen(true)}
          />
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--faint)" }}>
        <span>click image to expand</span>
        {onRegenerate && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onRegenerate()}
              disabled={busy}
              className="btn-secondary px-3 py-1 text-xs"
              title="A senior art director gives a completely different concept for the same topic"
            >
              {busy ? "Generating…" : "↻ Different concept"}
            </button>
            <button
              type="button"
              onClick={() => setCustom((v) => !v)}
              className="rounded-lg border border-[var(--line)] px-3 py-1 text-xs transition hover:border-[var(--line-strong)]"
              style={{ color: "var(--muted)" }}
            >
              {custom ? "Cancel" : "✎ My own prompt"}
            </button>
          </div>
        )}
      </div>

      {custom && (
        <div className="toast-in space-y-2 rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
          <label className="block text-[11px] font-semibold" style={{ color: "var(--muted)" }}>
            Describe the image you want
          </label>
          <textarea
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            rows={2}
            placeholder="e.g. A photorealistic control room at dawn, operators at workstations, warm dashboard glow…"
            className="w-full resize-y rounded-lg border bg-[var(--bg)] px-2.5 py-2 text-xs outline-none transition focus:border-[var(--accent)]"
            style={{ borderColor: "var(--line-strong)", color: "var(--ink)" }}
          />
          <div className="flex items-center justify-between gap-2">
            <p className="text-[10px]" style={{ color: "var(--faint)" }}>
              Your prompt is used as-is — no AI rewrite.
            </p>
            <button
              type="button"
              onClick={applyCustom}
              disabled={busy || !customPrompt.trim()}
              className="btn-dark rounded-lg px-3 py-1 text-xs disabled:opacity-50"
            >
              {busy ? "Generating…" : "Generate with this prompt"}
            </button>
          </div>
        </div>
      )}

      <details className="text-xs" style={{ color: "var(--faint)" }}>
        <summary className="cursor-pointer transition" style={{}} onMouseEnter={(e) => (e.currentTarget.style.color = "var(--ink-soft)")}>
          Image prompt
        </summary>
        <p className="mt-2 rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--muted)" }}>
          {prompt}
        </p>
      </details>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6" onClick={() => setOpen(false)}>
          <img src={url} alt="expanded" className="max-h-full max-w-full rounded-xl" />
        </div>
      )}
    </div>
  );
}