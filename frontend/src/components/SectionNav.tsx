import { useEffect, useRef, useState } from "react";

export type SectionRef = { id: string; step: string; label: string };

export function jumpToSection(id: string) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function useActiveSection(items: SectionRef[], offset = 170) {
  const [activeId, setActiveId] = useState(items[0]?.id ?? "");
  const lockUntil = useRef(0);

  useEffect(() => {
    const ids = items.map((i) => i.id);
    let raf = 0;
    const compute = () => {
      raf = 0;
      if (Date.now() < lockUntil.current) return;
      const els = ids
        .map((id) => document.getElementById(id))
        .filter((el): el is HTMLElement => Boolean(el));
      if (!els.length) return;

      const container = els[0].closest(".side-scroll") as HTMLElement | null;
      const vr = (container ?? document.documentElement).getBoundingClientRect();
      const viewBottom = Math.min(vr.bottom, window.innerHeight);
      const atBottom = container
        ? container.scrollTop + container.clientHeight >= container.scrollHeight - 4
        : window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;

      let next = ids[0];
      for (const id of ids) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top <= offset) next = id;
      }
      if (atBottom) {
        for (const id of ids) {
          const el = document.getElementById(id);
          if (el && el.getBoundingClientRect().top <= viewBottom - 24) next = id;
        }
      }
      setActiveId((prev) => (prev === next ? prev : next));
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(compute);
    };
    compute();
    document.addEventListener("scroll", onScroll, { capture: true, passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      document.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [items, offset]);

  const goTo = (id: string) => {
    lockUntil.current = Date.now() + 1000;
    setActiveId(id);
    jumpToSection(id);
  };

  return { activeId, goTo };
}

export default function SectionNav({ items }: { items: SectionRef[] }) {
  const [open, setOpen] = useState(false);
  const { activeId, goTo } = useActiveSection(items);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open]);

  const go = (id: string) => {
    setOpen(false);
    goTo(id);
  };

  const active = items.find((i) => i.id === activeId) ?? items[0];

  return (
    <div className="relative min-w-0 shrink-0" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={active ? `Jump to section — currently ${active.step}. ${active.label}` : "Jump to section"}
        title="Jump to section"
        className="btn-ghost !px-2.5 !py-1.5 text-xs"
      >
        <svg
          viewBox="0 0 16 16"
          className="h-4 w-4 shrink-0"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.7}
          strokeLinecap="round"
          aria-hidden="true"
        >
          {open ? (
            <>
              <path d="M3.5 3.5l9 9" />
              <path d="M12.5 3.5l-9 9" />
            </>
          ) : (
            <>
              <path d="M2.5 4h11" />
              <path d="M2.5 8h11" />
              <path d="M2.5 12h11" />
            </>
          )}
        </svg>
        <span className="hidden max-w-[10rem] truncate font-semibold sm:inline">
          {active ? `${active.step}. ${active.label}` : "Sections"}
        </span>
        <svg
          viewBox="0 0 16 16"
          className={`h-3 w-3 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.7}
          strokeLinecap="round"
          aria-hidden="true"
        >
          <path d="M4 6.5l4 4 4-4" />
        </svg>
      </button>

      {open ? (
        <div
          className="absolute left-0 top-full z-50 mt-1.5 w-64 max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-xl border py-1 shadow-lg"
          style={{ background: "var(--surface)", borderColor: "var(--line)" }}
        >
          <p
            className="px-3 pb-1 pt-1.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{ color: "var(--faint)" }}
          >
            Review sections
          </p>
          {items.map((s) => {
            const isActive = s.id === activeId;
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => go(s.id)}
                aria-current={isActive ? "true" : undefined}
                className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-xs transition hover:bg-[var(--surface-2)]"
                style={{
                  color: "var(--ink)",
                  background: isActive ? "var(--surface-2)" : "transparent",
                }}
              >
                <span className="section-step !h-5 !w-5 !text-[10px]" aria-hidden="true">
                  {s.step}
                </span>
                <span className="min-w-0 flex-1 truncate font-semibold">{s.label}</span>
                {isActive ? (
                  <span className="shrink-0 text-[9px]" style={{ color: "var(--accent-ink)" }}>
                    ●
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
