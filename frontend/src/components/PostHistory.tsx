import type { PostListResponse } from "../types";
import { timeAgo } from "../utils/format";
import StatusBadge from "./StatusBadge";

interface Props {
  data: PostListResponse | null;
  loading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRefresh: () => void;
}

export default function PostHistory({ data, loading, selectedId, onSelect, onRefresh }: Props) {
  const counts = data?.counts;
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="label mb-0.5">History</p>
          <h2 className="text-base font-bold">Your posts</h2>
        </div>
        <button type="button" onClick={onRefresh} disabled={loading} className="btn-secondary px-3 py-1.5 text-xs">
          {loading ? "Refreshing…" : "↻ Refresh"}
        </button>
      </div>

      {counts && (
        <div className="grid grid-cols-4 gap-2 text-center">
          {[
            ["All", counts.total],
            ["Review", counts.ready_for_review],
            ["Published", counts.published],
            ["Failed", counts.failed],
          ].map(([label, n]) => (
            <div key={label} className="rounded-xl border border-[var(--line)] bg-[var(--surface)] px-2 py-2">
              <div className="text-lg font-bold text-[var(--ink)]">{n}</div>
              <div className="label !text-[10px]">{label}</div>
            </div>
          ))}
        </div>
      )}

      {!data?.items.length ? (
        <p className="rounded-xl border border-dashed border-[var(--line-strong)] p-6 text-center text-sm text-[var(--faint)]">
          No posts yet — generate your first one.
        </p>
      ) : (
        <div className="max-h-[42vh] overflow-y-auto rounded-xl border border-[var(--line)]">
          <ul className="divide-hair divide-y bg-[var(--surface)]">
          {data.items.map((p) => (
            <li key={p.record_id}>
              <button
                type="button"
                onClick={() => onSelect(p.record_id)}
                className={`w-full px-3 py-2.5 text-left transition ${
                  selectedId === p.record_id ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--surface-2)]"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-mono text-xs text-[var(--muted)]">{p.record_id}</span>
                  <StatusBadge status={p.record_status} />
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <span
                    className={`tag !px-1.5 !py-0.5 !text-[10px] ${
                      p.priority === "High"
                        ? "tag--peach"
                        : p.priority === "Low"
                          ? "tag--slate"
                          : "tag--butter"
                    }`}
                  >
                    {p.priority}
                  </span>
                  <span className="tag tag--lavender !px-1.5 !py-0.5 !text-[10px]">{p.post_type}</span>
                  <span className="truncate text-xs text-[var(--faint)]">{p.user_query}</span>
                </div>
                <div className="mt-0.5 text-[10px]" style={{ color: "var(--faint)" }}>{timeAgo(p.created_at)}</div>
              </button>
            </li>
          ))}
        </ul>
        </div>
      )}
    </div>
  );
}