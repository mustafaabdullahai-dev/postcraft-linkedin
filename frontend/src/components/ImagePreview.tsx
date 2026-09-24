import { useState } from "react";

interface Props {
  url: string;
  prompt: string;
  busy?: boolean;
  onRegenerate?: () => void;
}

export default function ImagePreview({ url, prompt, busy, onRegenerate }: Props) {
  const [open, setOpen] = useState(false);
  const isSvg = url.startsWith("data:image/svg") || url.endsWith(".svg");

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
      <div className="flex items-center justify-between gap-2 text-xs" style={{ color: "var(--faint)" }}>
        <span>click image to expand</span>
        {onRegenerate && (
          <button type="button" onClick={onRegenerate} disabled={busy} className="btn-secondary px-3 py-1 text-xs">
            {busy ? "Regenerating…" : "↻ Regenerate"}
          </button>
        )}
      </div>
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