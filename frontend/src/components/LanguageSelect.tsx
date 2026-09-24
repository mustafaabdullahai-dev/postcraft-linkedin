import { useEffect, useMemo, useRef, useState } from "react";
import { LANGUAGES, LANGUAGE_TABS } from "../types";

interface Props {
  value: string;
  onChange: (language: string) => void;
}

export default function LanguageSelect({ value, onChange }: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return LANGUAGES;
    return LANGUAGES.filter((l) => l.toLowerCase().includes(q));
  }, [query]);

  const isTab = (l: string) => (LANGUAGE_TABS as readonly string[]).includes(l);
  const shown = isTab(value) ? "" : value;

  return (
    <div className="space-y-2">
      <p className="label">Language</p>

      <div className="flex flex-wrap gap-1.5">
        {LANGUAGE_TABS.map((l) => (
          <button
            key={l}
            type="button"
            onClick={() => {
              onChange(l);
              setOpen(false);
            }}
            className="rounded-full border px-3 py-1 text-[12px] font-medium transition-colors"
            style={{
              borderColor: value === l ? "var(--accent)" : "var(--line-2)",
              background: value === l ? "var(--accent-soft)" : "var(--surface)",
              color: value === l ? "var(--accent-ink)" : "var(--muted)",
            }}
          >
            {l}
          </button>
        ))}
      </div>

      <div ref={boxRef} className="relative">
        <div className="relative">
          <input
            type="text"
            value={open || query ? query : shown}
            placeholder={isTab(value) ? "Search 100+ languages…" : value || "Search 100+ languages…"}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => {}}
            onKeyDown={(e) => {
              if (e.key === "Enter" && results[0]) {
                onChange(results[0]);
                setQuery("");
                setOpen(false);
              }
              if (e.key === "Escape") setOpen(false);
            }}
            className="input h-10 pr-20 font-medium"
          />
          <svg
            viewBox="0 0 24 24"
            className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2"
            style={{ color: "var(--faint)" }}
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
        </div>

        {open && (
          <div
            className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-xl border py-1 shadow-xl"
            style={{ background: "var(--surface)", borderColor: "var(--line-2)" }}
          >
            {results.length === 0 && (
              <p className="px-3 py-2 text-xs" style={{ color: "var(--faint)" }}>
                No match — press Enter to use “{query}”.
              </p>
            )}
            {results.map((l) => (
              <button
                key={l}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  onChange(l);
                  setQuery("");
                  setOpen(false);
                }}
                className="block w-full px-3 py-1.5 text-left text-sm transition"
                style={{
                  background: value === l ? "var(--accent-soft)" : "transparent",
                  color: value === l ? "var(--accent-ink)" : "var(--ink-soft)",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-2)")}
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = value === l ? "var(--accent-soft)" : "transparent")
                }
              >
                {l}
                {value === l && <span className="float-right font-bold">✓</span>}
              </button>
            ))}
            {query.trim() && !LANGUAGES.some((l) => l.toLowerCase() === query.trim().toLowerCase()) && (
              <button
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  onChange(query.trim());
                  setQuery("");
                  setOpen(false);
                }}
                className="block w-full border-t px-3 py-2 text-left text-xs font-semibold"
                style={{ borderColor: "var(--line)", color: "var(--accent)", background: "var(--accent-soft)" }}
              >
                + Use custom “{query.trim()}”…
              </button>
            )}
            <p
              className="border-t px-3 py-1.5 text-[10px]"
              style={{ borderColor: "var(--line)", color: "var(--faint)" }}
            >
              {query.trim() ? `${results.length} of ${LANGUAGES.length}` : `${LANGUAGES.length}`} languages — keep typing
              to narrow
            </p>
          </div>
        )}
      </div>
      <p className="hint">Applies to the post text and to any words shown in the generated image.</p>
    </div>
  );
}