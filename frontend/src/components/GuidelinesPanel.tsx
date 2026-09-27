import { useEffect } from "react";

import type { GuidelineGroup } from "../types";

interface Props {
  groups: GuidelineGroup[] | null;
  source?: string;
  disclaimer?: string;
  loading?: boolean;
  onClose: () => void;
}

/** Modal listing the LinkedIn posting guidelines the agent enforces. */
export default function GuidelinesPanel({ groups, source, disclaimer, loading, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[90] flex items-end justify-center bg-black/60 sm:items-center sm:p-6"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="LinkedIn posting guidelines"
    >
      <div
        className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-2xl border sm:rounded-2xl"
        style={{ background: "var(--surface)", borderColor: "var(--line)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <header
          className="flex items-start justify-between gap-3 border-b px-5 py-4"
          style={{ borderColor: "var(--line)" }}
        >
          <div className="min-w-0">
            <h2 className="text-base font-bold" style={{ color: "var(--ink)" }}>
              LinkedIn compliance
            </h2>
            <p className="hint mt-0.5">The guidelines the agent follows before anything is published.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close guidelines"
            className="btn-ghost shrink-0 !px-2.5 !py-1 text-sm"
          >
            ✕
          </button>
        </header>

        <div className="overflow-y-auto px-5 py-4">
          {disclaimer && (
            <p
              className="mb-5 rounded-xl border px-3.5 py-3 text-[11px] leading-snug"
              style={{
                borderColor: "var(--line)",
                background: "var(--accent-soft)",
                color: "var(--accent-ink)",
              }}
            >
              {disclaimer}
            </p>
          )}
          {loading && !groups && (
            <p className="py-6 text-center text-xs" style={{ color: "var(--faint)" }}>
              Loading guidelines…
            </p>
          )}
          {(groups ?? []).map((g) => (
            <section key={g.id} className="mb-5 last:mb-0">
              <h3
                className="mb-2 text-[11px] font-semibold uppercase tracking-wide"
                style={{ color: "var(--faint)" }}
              >
                {g.title}
              </h3>
              <ul className="space-y-2.5">
                {g.items.map((it) => (
                  <li
                    key={it.title}
                    className="rounded-xl border p-3"
                    style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
                  >
                    <p className="text-xs font-semibold" style={{ color: "var(--ink)" }}>
                      {it.title}
                    </p>
                    <p className="mt-0.5 text-[11px] leading-snug" style={{ color: "var(--muted)" }}>
                      {it.detail}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          ))}
          {source && (
            <p className="mt-4 text-[10px]" style={{ color: "var(--faint)" }}>
              Source: {source}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
