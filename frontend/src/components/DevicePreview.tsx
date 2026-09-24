import { useEffect } from "react";
import type { ReactNode } from "react";

export type DeviceId = "phone" | "tablet" | "desktop";

export const DEVICES: Array<{ id: DeviceId; label: string; width: number }> = [
  { id: "phone", label: "Mobile", width: 360 },
  { id: "tablet", label: "Tablet", width: 640 },
  { id: "desktop", label: "Desktop", width: 820 },
];

const ICONS: Record<DeviceId, JSX.Element> = {
  phone: (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
      <path d="M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zm5 18.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2z" />
    </svg>
  ),
  tablet: (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
      <path d="M5 3h14a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm9.5 1a.5.5 0 1 0 0 1h-1a.5.5 0 1 0 0 1h1a.5.5 0 1 0 0-1z" />
    </svg>
  ),
  desktop: (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
      <path d="M3 4h18a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1h-7l.5 2.5H17a1 1 0 0 1 0 2H7a1 1 0 0 1 0-2h2.5L10 17H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z" />
    </svg>
  ),
};

interface Props {
  device: DeviceId;
  onChange: (d: DeviceId) => void;
  children: ReactNode;
}

export default function DevicePreview({ device, onChange, children }: Props) {
  const current = DEVICES.find((d) => d.id === device)!;

  useEffect(() => {
    try {
      const stored = localStorage.getItem("li_device") as DeviceId | null;
      if (stored && DEVICES.some((d) => d.id === stored)) onChange(stored);
    } catch {
      /* ignore */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pick = (id: DeviceId) => {
    try {
      localStorage.setItem("li_device", id);
    } catch {
      /* ignore */
    }
    onChange(id);
  };

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div
          className="flex items-center gap-0.5 rounded-full border p-0.5"
          style={{ borderColor: "var(--line-2)" }}
        >
          {DEVICES.map((d) => {
            const active = d.id === device;
            return (
              <button
                key={d.id}
                type="button"
                onClick={() => pick(d.id)}
                className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition sm:px-3"
                style={{
                  background: active ? "var(--accent-soft)" : "transparent",
                  color: active ? "var(--accent-ink)" : "var(--faint)",
                }}
              >
                {ICONS[d.id]}
                <span className="hidden sm:inline">{d.label}</span>
              </button>
            );
          })}
        </div>
        <span className="hint hidden md:inline">How it looks on a {current.label.toLowerCase()}</span>
      </div>

      <div className="flex justify-center">
        <div
          className="w-full overflow-hidden border transition-all duration-300"
          style={{
            width: `min(${current.width}px, 100%)`,
            borderColor: "var(--line-2)",
            borderRadius: device === "phone" ? "1.75rem" : "1rem",
            boxShadow: "0 10px 30px -18px rgba(0,0,0,0.35)",
          }}
        >
          {/* device chrome */}
          <div
            className="flex h-9 items-center justify-between border-b px-3"
            style={{ background: "var(--surface-2)", borderColor: "var(--line)" }}
          >
            {device === "phone" ? (
              <span className="mx-auto block h-1.5 w-20 rounded-full" style={{ background: "var(--line-strong)" }} />
            ) : (
              <>
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--t-rose-d)" }} />
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--t-butter-d)" }} />
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--t-mint-d)" }} />
                </div>
                <span className="max-w-[40%] truncate font-mono text-[10px] tracking-widest" style={{ color: "var(--faint)" }}>
                  linkedin.com
                </span>
              </>
            )}
            <span
              className="font-mono text-[10px]"
              style={{ color: "var(--faint)", position: device === "phone" ? "absolute" : "static", right: 12 }}
            >
              {current.width}px
            </span>
          </div>

          {/* device screen */}
          <div className="min-w-0 overflow-x-hidden overflow-y-auto" style={{ maxHeight: 560 }}>
            {children}
          </div>

          {device === "phone" && (
            <div className="flex justify-center border-t py-1" style={{ borderColor: "var(--line)" }}>
              <span className="h-1 w-16 rounded-full" style={{ background: "var(--line-strong)" }} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}