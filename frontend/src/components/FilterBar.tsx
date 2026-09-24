import type { PostFilters } from "../types";
import { POST_TYPES, PRIORITIES } from "../types";

const STATUSES = ["", "READY_FOR_REVIEW", "EDITED", "PUBLISHED", "FAILED"];

interface Props {
  filters: PostFilters;
  onChange: (filters: PostFilters) => void;
}

export default function FilterBar({ filters, onChange }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-[var(--faint)]">
        Priority
        <select
          value={filters.priority ?? ""}
          onChange={(e) => onChange({ ...filters, priority: e.target.value || undefined })}
          className="select"
        >
          <option value="">All</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-[var(--faint)]">
        Type
        <select
          value={filters.post_type ?? ""}
          onChange={(e) => onChange({ ...filters, post_type: e.target.value || undefined })}
          className="select"
        >
          <option value="">All</option>
          {POST_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-[var(--faint)]">
        Status
        <select
          value={filters.status ?? ""}
          onChange={(e) => onChange({ ...filters, status: e.target.value || undefined })}
          className="select"
        >
          {STATUSES.map((s) => (
            <option key={s || "all"} value={s}>
              {s ? s.replaceAll("_", " ") : "All"}
            </option>
          ))}
        </select>
      </label>

      {(filters.priority || filters.post_type || filters.status) && (
        <button
          type="button"
          onClick={() => onChange({})}
          className="rounded-lg px-2 py-1 text-[11px] font-medium text-[var(--accent)] hover:text-[var(--accent-ink)]"
        >
          clear
        </button>
      )}
    </div>
  );
}