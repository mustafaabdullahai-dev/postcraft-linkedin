export interface SubTabDef<T extends string> {
  id: T;
  label: string;
  icon?: string;
  count?: number;
}

interface Props<T extends string> {
  tabs: Array<SubTabDef<T>>;
  value: T;
  onChange: (id: T) => void;
  ariaLabel?: string;
}

export default function SubTabs<T extends string>({ tabs, value, onChange, ariaLabel = "Section" }: Props<T>) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="flex w-fit max-w-full items-center gap-0.5 overflow-x-auto rounded-full p-0.5"
      style={{
        background: "var(--surface)",
      }}
    >
      {tabs.map((t) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(t.id)}
            className="flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-semibold transition-all"
            style={{
              background: active ? "linear-gradient(135deg,var(--accent),var(--accent-2))" : "transparent",
              color: active ? "var(--btn-ink)" : "var(--faint)",
            }}
          >
            {t.icon && (
              <span className={active ? "" : "opacity-80"} aria-hidden="true">
                {t.icon}
              </span>
            )}
            {t.label}
            {t.count !== undefined && t.count > 0 && (
              <span
                className="rounded-full px-1 text-[9px] leading-[14px]"
                style={{
                  background: active ? "rgba(0,0,0,0.18)" : "var(--surface-2)",
                  color: active ? "var(--btn-ink)" : "var(--muted)",
                }}
              >
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
