import { useEffect, useState } from "react";
import type { ThemeMode } from "../theme";
import { applyTheme, getStoredTheme, storeTheme, systemTheme } from "../theme";

const OPTIONS: Array<{ mode: ThemeMode; label: string; icon: JSX.Element }> = [
  {
    mode: "system",
    label: "System",
    icon: (
      <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
        <path d="M3 4h18a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zm7 14h4v1a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1z" />
      </svg>
    ),
  },
  {
    mode: "light",
    label: "Light",
    icon: (
      <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
        <path d="M12 5a7 7 0 1 1 0 14 7 7 0 0 1 0-14zm0 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm9.5 5h.5a1 1 0 0 1 0 2h-.5a1 1 0 0 1 0-2zm-20 0h.5a1 1 0 0 1 0 2H1.5a1 1 0 0 1 0-2zM12 1.5a1 1 0 0 1 1 1V3a1 1 0 0 1-2 0v-.5a1 1 0 0 1 1-1zm0 20a1 1 0 0 1 1 1v.5a1 1 0 0 1-2 0v-.5a1 1 0 0 1 1-1zM5.6 3.9a1 1 0 0 1 1.4 0l.4.4a1 1 0 0 1-1.4 1.4l-.4-.4a1 1 0 0 1 0-1.4zm11.4 15.4a1 1 0 0 1 1.4 0l.4.4a1 1 0 0 1-1.4 1.4l-.4-.4a1 1 0 0 1 0-1.4zM3.9 18.4a1 1 0 0 1 0-1.4l.4-.4a1 1 0 0 1 1.4 1.4l-.4.4a1 1 0 0 1-1.4 0zm15.4-11.4a1 1 0 0 1 0-1.4l.4-.4a1 1 0 0 1 1.4 1.4l-.4.4a1 1 0 0 1-1.4 0z" />
      </svg>
    ),
  },
  {
    mode: "dark",
    label: "Dark",
    icon: (
      <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
        <path d="M12.3 2.1a.8.8 0 0 1 .4 1 8.2 8.2 0 0 0 8.2 8.2.8.8 0 0 1 .9 1.1 10.3 10.3 0 1 1-11.4-11.4.8.8 0 0 1 1.1.9-.7.7 0 0 0 .8 1.1z" />
      </svg>
    ),
  },
];

export default function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(() => {
    if (typeof window === "undefined") return "system";
    return getStoredTheme();
  });

  useEffect(() => {
    applyTheme(mode);
    if (mode !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = () => applyTheme("system");
    mq.addEventListener("change", listener);
    return () => mq.removeEventListener("change", listener);
  }, [mode]);

  const select = (m: ThemeMode) => {
    setMode(m);
    storeTheme(m);
  };

  return (
    <div className="flex items-center gap-0.5 rounded-full border p-0.5" style={{ borderColor: "var(--line-2)" }}>
      {OPTIONS.map(({ mode: m, label, icon }) => {
        const active = mode === m;
        return (
          <button
            key={m}
            type="button"
            title={label}
            aria-label={label}
            onClick={() => select(m)}
            className="flex h-8 w-8 items-center justify-center rounded-full transition"
            style={{
              background: active ? "var(--accent-soft)" : "transparent",
              color: active ? "var(--accent-ink)" : "var(--faint)",
            }}
          >
            {icon}
          </button>
        );
      })}
      <span className="hidden pl-1 pr-2 text-[10px] font-semibold sm:block" style={{ color: "var(--faint)" }}>
        {mode === "system" ? `System · ${systemTheme()}` : mode}
      </span>
    </div>
  );
}