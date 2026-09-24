import { useState } from "react";
import { api } from "../services/api";
import type { FormattingPrefs, PostEditSuggestions as Suggestions, PostRecord } from "../types";

interface Props {
  recordId: string;
  disabled?: boolean;
  formatting: FormattingPrefs;
  onApply: (draft: string) => void;
  onReworked: (record: PostRecord) => void;
}

export default function EditSuggestions({ recordId, disabled, formatting, onApply, onReworked }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [reworking, setReworking] = useState(false);
  const [data, setData] = useState<Suggestions | null>(null);
  const [applied, setApplied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reworkError, setReworkError] = useState<string | null>(null);

  const fetchAndApply = async () => {
    if (disabled || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.suggestEdits(recordId);
      setData(res);
      setOpen(true);
      if (res.improved_draft?.trim()) {
        onApply(res.improved_draft);
        setApplied(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load suggestions");
      setOpen(true);
    } finally {
      setLoading(false);
    }
  };

  const regenerate = async () => {
    if (!data || reworking) return;
    setReworking(true);
    setReworkError(null);
    try {
      const rec = await api.rework(recordId, data.improved_draft, formatting);
      onReworked(rec);
      setData(null);
      setApplied(false);
      setOpen(false);
    } catch (e) {
      setReworkError(e instanceof Error ? e.message : "Regeneration failed");
    } finally {
      setReworking(false);
    }
  };

  return (
    <div className="card p-4">
      <button type="button" onClick={fetchAndApply} disabled={disabled || loading} className="btn-dark w-full">
        {loading ? "Asking the editor…" : "✨ Suggest & apply"}
      </button>
      {!disabled && (
        <p className="hint mt-2">
          The editor rewrites the current draft in one go — it updates the text above automatically, then you review and
          save.
        </p>
      )}

      {error && <p className="mt-2 text-xs text-[var(--bad)]">{error}</p>}

      {open && data && (
        <div className="toast-in mt-3 space-y-3">
          <div
            className="rounded-xl border p-3"
            style={{
              borderColor: applied ? "var(--ok-soft)" : "var(--line)",
              background: applied ? "var(--ok-soft)" : "var(--surface-2)",
            }}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold leading-snug" style={{ color: "var(--ink)" }}>
                "{data.summary}"
              </p>
              {applied && (
                <span className="tag tag--mint shrink-0">Applied ✓</span>
              )}
            </div>
            <ul className="mt-2 space-y-1.5">
              {data.notes.map((note) => (
                <li key={note} className="flex gap-2 text-xs" style={{ color: "var(--muted-2)" }}>
                  <span style={{ color: "var(--accent)" }}>•</span>
                  <span>{note}</span>
                </li>
              ))}
            </ul>
          </div>

          <button
            type="button"
            onClick={regenerate}
            disabled={reworking}
            className="btn-primary w-full py-2 text-xs"
          >
            {reworking ? "Regenerating…" : "↻ Rewrite with my style options"}
          </button>
          <p className="text-[11px] leading-snug" style={{ color: "var(--faint)" }}>
            The advance option re-runs the draft through the model applying the style &amp; length settings above, then
            refreshes hashtags and re-validates.
          </p>

          {reworkError && <p className="text-xs text-[var(--bad)]">{reworkError}</p>}
        </div>
      )}
    </div>
  );
}