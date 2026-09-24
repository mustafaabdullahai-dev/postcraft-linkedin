import { humanizeStatus, statusColor } from "../utils/format";

const TAG_DOT: Record<string, string> = {
  "tag--lavender": "var(--t-lavender-d)",
  "tag--mint": "var(--t-mint-d)",
  "tag--peach": "var(--t-peach-d)",
  "tag--sky": "var(--t-sky-d)",
  "tag--butter": "var(--t-butter-d)",
  "tag--rose": "var(--t-rose-d)",
  "tag--slate": "var(--t-slate-d)",
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold"
      style={{ background: "var(--surface-2)", color: "var(--muted)" }}
      title={status}
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: TAG_DOT[statusColor(status)] ?? "var(--t-slate-d)" }} />
      {humanizeStatus(status)}
    </span>
  );
}