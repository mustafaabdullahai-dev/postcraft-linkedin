import { useEffect, useMemo, useRef, useState } from "react";

export type PaletteCommand = {
  id: string;
  icon: string;
  title: string;
  hint?: string;
  run: () => void;
};

interface Props {
  open: boolean;
  onClose: () => void;
  commands: PaletteCommand[];
  onSubmitText?: (text: string) => void;
}

function EmptyBox() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current" aria-hidden="true">
      <path d="M16.3 14.9a7.5 7.5 0 1 0-1.4 1.4l4.4 4.4a1 1 0 0 0 1.4-1.4zm-6.3.6a5.5 5.5 0 1 1 0-11 5.5 5.5 0 0 1 0 11z" />
    </svg>
  );
}

export default function CommandMenu({ open, onClose, commands, onSubmitText }: Props) {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const groups = useMemo(() => {
    const q = query.trim();
    const lq = q.toLowerCase();
    const matched = lq
      ? commands
          .map((c) => ({ c, score: c.title.toLowerCase().includes(lq) ? c.title.toLowerCase().indexOf(lq) : -1 }))
          .filter((x) => x.score >= 0)
          .sort((a, b) => a.score - b.score)
          .map((x) => x.c)
      : commands;
    const quick: PaletteCommand[] =
      q && onSubmitText
        ? [
            {
              id: "quick-generate",
              icon: "✦",
              title: `Generate: “${q.slice(0, 42)}${q.length > 42 ? "…" : ""}”`,
              hint: "Create a new draft from this topic",
              run: () => onSubmitText(q),
            },
          ]
        : [];
    const nav = quick.length ? matched : matched;
    const groups: Array<{ label: string; items: PaletteCommand[] }> = [];
    if (quick.length) groups.push({ label: "Create", items: quick });
    groups.push({ label: lq ? "Go to" : "Navigate", items: nav });
    return groups;
  }, [commands, onSubmitText, query]);

  const items = useMemo(() => groups.flatMap((g) => g.items), [groups]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setIndex(0);
    const t = setTimeout(() => inputRef.current?.focus(), 10);
    return () => clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (index >= items.length) setIndex(Math.max(0, items.length - 1));
  }, [items, index]);

  if (!open) return null;

  const pick = (cmd: PaletteCommand) => {
    cmd.run();
    onClose();
  };

  let cursor = 0;

  return (
    <div
      className="palette-overlay fixed inset-0 z-[70] flex items-start justify-center bg-black/50 px-4 pt-[15vh]"
      style={{ backdropFilter: "blur(5px)" }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Quick commands"
    >
      <div
        className="palette-pop w-full max-w-xl overflow-hidden rounded-2xl border"
        style={{
          background: "var(--surface)",
          borderColor: "var(--line)",
          boxShadow:
            "0 0 0 1px var(--bg), 0 0 0 2px var(--logo-ring), 0 0 0 5px color-mix(in srgb, var(--accent) 12%, transparent), 0 24px 60px -16px rgba(10,16,32,0.55)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* header strip */}
        <div className="flex items-center justify-between border-b px-4 py-2" style={{ borderColor: "var(--line)" }}>
          <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: "var(--faint)" }}>
            <img src="/favicon.png" alt="" className="h-4 w-4 rounded" />
            PostCraft · Quick actions
          </span>
          <kbd className="kbd !px-1.5 !py-0.5 !text-[10px]">Esc</kbd>
        </div>

        {/* search input */}
        <div className="flex items-center gap-2.5 border-b px-4" style={{ borderColor: "var(--line)" }}>
          <span style={{ color: "var(--faint)" }}>
            <EmptyBox />
          </span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setIndex(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setIndex((i) => Math.min(i + 1, items.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setIndex((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter" && items[index]) {
                pick(items[index]);
              } else if (e.key === "Escape") {
                onClose();
              }
            }}
            placeholder="Jump to a tab… or type a topic to generate"
            className="w-full bg-transparent py-3.5 text-sm outline-none"
            style={{ color: "var(--ink)" }}
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Clear search"
              className="rounded-md px-1 text-sm leading-none transition hover:text-[var(--accent)]"
              style={{ color: "var(--faint)" }}
            >
              ✕
            </button>
          )}
        </div>

        {/* grouped results */}
        <div className="max-h-[42vh] overflow-y-auto p-1.5">
          {items.length === 0 && (
            <div className="px-3 py-8 text-center text-xs" style={{ color: "var(--faint)" }}>
              No match — try a tab name or a topic.
            </div>
          )}
          {groups.map((g) => {
            if (!g.items.length) return null;
            return (
              <div key={g.label} className="mb-1">
                <p className="px-3 pb-1 pt-1.5 text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: "var(--faint)" }}>
                  {g.label}
                </p>
                {g.items.map((cmd) => {
                  const i = cursor;
                  cursor += 1;
                  const active = i === index;
                  return (
                    <button
                      key={`${cmd.id}-${i}`}
                      type="button"
                      onClick={() => pick(cmd)}
                      onMouseEnter={() => setIndex(i)}
                      className="relative flex w-full items-center gap-3 rounded-xl px-2.5 py-2.5 text-left transition"
                      style={{
                        background: active ? "var(--accent-soft)" : "transparent",
                      }}
                    >
                      {active && (
                        <span
                          className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-full"
                          style={{ background: "var(--accent)" }}
                        />
                      )}
                      <span
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm"
                        style={{
                          background: active ? "linear-gradient(135deg,var(--accent),var(--accent-2))" : "var(--surface-2)",
                          color: active ? "var(--btn-ink)" : "var(--muted)",
                        }}
                      >
                        {cmd.icon}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium" style={{ color: "var(--ink)" }}>
                          {cmd.title}
                        </span>
                        {cmd.hint && (
                          <span className="block truncate text-[11px]" style={{ color: "var(--faint)" }}>
                            {cmd.hint}
                          </span>
                        )}
                      </span>
                      {active && <kbd className="kbd !px-1.5 !py-0.5 !text-[10px]">↵</kbd>}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>

        {/* footer hints */}
        <div className="flex items-center gap-3 border-t px-4 py-2 text-[10px]" style={{ borderColor: "var(--line)", color: "var(--faint)" }}>
          <span className="flex items-center gap-1"><kbd className="kbd !px-1 !py-0 !text-[9px]">↑↓</kbd> navigate</span>
          <span className="flex items-center gap-1"><kbd className="kbd !px-1 !py-0 !text-[9px]">↵</kbd> select</span>
          <span className="flex items-center gap-1"><kbd className="kbd !px-1 !py-0 !text-[9px]">Esc</kbd> close</span>
          <span className="ml-auto flex items-center gap-1">
            <kbd className="kbd !px-1 !py-0 !text-[9px]">⌘K</kbd> anywhere
          </span>
        </div>
      </div>
    </div>
  );
}