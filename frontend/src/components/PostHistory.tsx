import { useEffect, useRef, useState } from "react";
import type { PostFilters, PostRecord, StatusCounts } from "../types";
import { api } from "../services/api";
import { formatLocalTime } from "../utils/format";
import StatusBadge from "./StatusBadge";
import Skeleton from "./Skeleton";

const PAGE_SIZE = 25;
const EXPORT_FORMATS: Array<{ id: "csv" | "json" | "md"; label: string }> = [
  { id: "csv", label: "CSV (spreadsheet)" },
  { id: "json", label: "JSON (data)" },
  { id: "md", label: "Markdown (notes)" },
];

interface Props {
  filters: PostFilters;
  reloadKey: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDuplicate: (rec: PostRecord) => void;
  onToast: (text: string, kind?: "success" | "error", action?: { label: string; onClick: () => void }) => void;
  onTotal?: (n: number) => void;
}

function CopyIcon() {
  return (
    <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
      <rect x="5" y="5" width="9" height="9" rx="2" />
      <path d="M11 5V3.5A1.5 1.5 0 0 0 9.5 2h-6A1.5 1.5 0 0 0 2 3.5v6A1.5 1.5 0 0 0 3.5 11H5" />
    </svg>
  );
}

function DuplicateIcon() {
  return (
    <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
      <rect x="2" y="2" width="9" height="9" rx="2" />
      <path d="M5.5 9.5h0" />
      <path d="M5 11.5V12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-.5" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
      <path d="M2.5 4h11M6.5 4V2.8a.8.8 0 0 1 .8-.8h1.4a.8.8 0 0 1 .8.8V4M4 4l.6 9a1 1 0 0 0 1 .9h4.8a1 1 0 0 0 1-.9L12 4M6.5 7v5M9.5 7v5" />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
      <path d="M11 2.5l2.5 2.5L6 12.5 3 13l.5-3L11 2.5zM8.5 5l2.5 2.5" />
    </svg>
  );
}

function Thumb({ rec }: { rec: PostRecord }) {
  if (rec.image_url) {
    return (
      <img
        src={rec.image_url}
        alt=""
        loading="lazy"
        className="h-11 w-11 shrink-0 rounded-lg border border-[var(--line)] object-cover"
      />
    );
  }
  const letter = (rec.user_query || rec.topic || "P").trim().charAt(0).toUpperCase();
  return (
    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[var(--line)] bg-gradient-to-br from-[var(--accent-soft)] to-[var(--surface-2)] text-sm font-bold text-[var(--accent-ink)]">
      {letter}
    </span>
  );
}

export default function PostHistory({ filters, reloadKey, selectedId, onSelect, onDuplicate, onToast, onTotal }: Props) {
  const [items, setItems] = useState<PostRecord[]>([]);
  const [counts, setCounts] = useState<StatusCounts | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [confirmAll, setConfirmAll] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const exportRef = useRef<HTMLDivElement | null>(null);
  const [tick, setTick] = useState(0);
  const confirmTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seq = useRef(0);

  const activeFilters: PostFilters = { ...filters, q: search.trim() || undefined, sort };
  const hasMore = items.length < total;

  useEffect(() => {
    setConfirmId(null);
    setConfirmAll(false);
    setCopiedId(null);
    setItems([]);
    setTotal(0);
    setCounts(null);
    setLoading(true);
    const run = ++seq.current;
    void api
      .list(PAGE_SIZE, 0, activeFilters)
      .then((d) => {
        if (run !== seq.current) return;
        setItems(d.items);
        setTotal(d.total);
        setCounts(d.counts);
        onTotal?.(d.total);
      })
      .catch(() => {
        if (run !== seq.current) return;
        onToast("Couldn't load history", "error");
      })
      .finally(() => {
        if (run === seq.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, sort, search, reloadKey, tick]);

  const loadMore = () => {
    setLoading(true);
    const run = ++seq.current;
    void api
      .list(PAGE_SIZE, items.length, activeFilters)
      .then((d) => {
        if (run !== seq.current) return;
        setItems((prev) => [...prev, ...d.items]);
        setTotal(d.total);
      })
      .catch(() => {
        if (run !== seq.current) return;
        onToast("Couldn't load more", "error");
      })
      .finally(() => {
        if (run === seq.current) setLoading(false);
      });
  };

  const copyPost = async (rec: PostRecord) => {
    const text = rec.final_post ?? rec.generated_post;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(rec.record_id);
      onToast("Post copied to clipboard");
      setTimeout(() => setCopiedId(null), 1600);
    } catch {
      onToast("Clipboard unavailable", "error");
    }
  };

  const deletePost = async (rec: PostRecord) => {
    if (rec.record_status === "PUBLISHED") {
      onToast("Published posts can't be deleted — keep them as your track record", "error");
      return;
    }
    if (confirmId !== rec.record_id) {
      setConfirmId(rec.record_id);
      onToast("Tap again to confirm delete");
      if (confirmTimer.current) clearTimeout(confirmTimer.current);
      confirmTimer.current = setTimeout(() => setConfirmId(null), 3200);
      return;
    }
    if (confirmTimer.current) clearTimeout(confirmTimer.current);
    try {
      await api.deletePost(rec.record_id);
      setItems((prev) => prev.filter((x) => x.record_id !== rec.record_id));
      setTotal((t) => {
        const next = Math.max(0, t - 1);
        onTotal?.(next);
        return next;
      });
      onToast("Post deleted");
    } catch (e) {
      onToast(e instanceof Error ? e.message : "Delete failed", "error");
    } finally {
      setConfirmId(null);
      setCopiedId(null);
    }
  };

  const deleteAll = async () => {
    if (!confirmAll) {
      setConfirmAll(true);
      onToast("Tap again to delete everything shown", "error");
      if (confirmTimer.current) clearTimeout(confirmTimer.current);
      confirmTimer.current = setTimeout(() => setConfirmAll(false), 3200);
      return;
    }
    if (confirmTimer.current) clearTimeout(confirmTimer.current);
    try {
      const d = await api.deleteAll(activeFilters);
      setConfirmAll(false);
      setTick((t) => t + 1);
      onToast(d.deleted ? `Deleted ${d.deleted} post${d.deleted === 1 ? "" : "s"}` : "Nothing to delete");
    } catch (e) {
      setConfirmAll(false);
      onToast(e instanceof Error ? e.message : "Delete all failed", "error");
    }
  };

  const exportPosts = async (format: "csv" | "json" | "md") => {
    setExportOpen(false);
    try {
      await api.downloadExport(format);
      onToast("Export downloaded");
    } catch (e) {
      onToast(e instanceof Error ? e.message : "Export failed", "error");
    }
  };

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (exportRef.current && !exportRef.current.contains(e.target as Node)) setExportOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const wordCount = (rec: PostRecord) => {
    const body = rec.final_post ?? rec.generated_post;
    const words = body.trim().split(/\s+/).filter(Boolean).length;
    const hook = body.trim().slice(0, 90);
    return { words, hook };
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div>
            <p className="label mb-0.5">History</p>
            <h2 className="text-lg font-bold">Your posts</h2>
          </div>
          <span className="tag tag--slate !px-2 !py-0.5 !text-[10px]">{total}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {(["newest", "oldest"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSort(s)}
              className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold capitalize transition ${
                sort === s ? "bg-[var(--accent)] text-[var(--accent-ink)]" : "text-[var(--muted)] hover:bg-[var(--surface-2)]"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div ref={exportRef} className="relative">
          <button
            type="button"
            onClick={() => setExportOpen((s) => !s)}
            className="flex items-center gap-1 rounded-full border border-[var(--line-strong)] px-3 py-1.5 text-xs font-semibold text-[var(--muted)] transition hover:bg-[var(--surface-2)] hover:text-[var(--ink)]"
            aria-expanded={exportOpen}
          >
            ⭳ Export
          </button>
          {exportOpen && (
            <div
              className="absolute left-0 top-full z-30 mt-1 w-48 overflow-hidden rounded-xl border py-1 shadow-lg"
              style={{ background: "var(--surface)", borderColor: "var(--line)" }}
            >
              {EXPORT_FORMATS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => void exportPosts(f.id)}
                  className="block w-full px-3 py-2 text-left text-xs transition hover:bg-[var(--surface-2)]"
                  style={{ color: "var(--ink)" }}
                >
                  <span className="font-semibold">{f.label}</span>
                  <span className="block text-[10px]" style={{ color: "var(--faint)" }}>
                    {f.id === "csv" ? "for spreadsheets & sheets" : f.id === "json" ? "for apps & backups" : "for docs & notes"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
        <button
          type="button"
          title={
            total === 0
              ? "Nothing to delete"
              : confirmAll
                ? "Tap again to confirm — this can't be undone"
                : "Deletes every non-published post in the current view"
          }
          onClick={() => void deleteAll()}
          disabled={total === 0}
          className={`flex min-w-[7.75rem] items-center justify-center gap-1.5 rounded-full border px-3.5 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${
            confirmAll
              ? "border-[var(--danger)] bg-[var(--danger)] text-white shadow-[0_1px_8px_color-mix(in_srgb,var(--danger)_45%,transparent)]"
              : "border-[var(--line-strong)] bg-transparent text-[var(--danger)] hover:border-[var(--danger)] hover:bg-[var(--danger)] hover:text-white"
          }`}
        >
          <TrashIcon />{" "}
          {confirmAll ? (
            <span className="inline-flex items-center gap-1">
              Confirm delete?
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
            </span>
          ) : (
            "Delete all"
          )}
        </button>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search topics, text, hashtags…"
          className="input !h-9 !rounded-full !px-3.5 !py-1.5 !text-xs"
        />
        {search && (
          <button type="button" onClick={() => setSearch("")} className="btn-secondary px-2.5 py-1.5 text-xs">
            Clear
          </button>
        )}
      </div>

      {counts && (
        <div className="grid grid-cols-2 gap-2.5 text-center sm:grid-cols-5">
          {[
            ["All", total],
            ["Review", counts.ready_for_review],
            ["Scheduled", counts.scheduled],
            ["Published", counts.published],
            ["Failed", counts.failed],
          ].map(([label, n]) => (
            <div key={label} className="rounded-xl border border-[var(--line)] bg-[var(--surface)] px-2 py-2.5">
              <div className="text-xl font-bold text-[var(--ink)]">{n}</div>
              <div className="label !text-[10px]">{label}</div>
            </div>
          ))}
        </div>
      )}

      {loading && !items.length ? (
        <div className="space-y-2 rounded-xl border border-[var(--line)] p-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center gap-2.5 rounded-lg p-2.5" style={{ background: "var(--surface)" }}>
              <Skeleton className="skeleton h-9 w-9 shrink-0 !rounded-md" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-3 w-3/5" />
                <Skeleton className="h-2.5 w-2/5" />
              </div>
              <Skeleton className="h-4 w-16" />
            </div>
          ))}
        </div>
      ) : !items.length ? (
        <p className="rounded-xl border border-dashed border-[var(--line-strong)] p-6 text-center text-sm text-[var(--faint)]">
          {loading ? "Loading…" : search || filters.priority || filters.post_type || filters.status
            ? "No posts match these filters."
            : "No posts yet — generate your first one."}
        </p>
      ) : (
        <div className="max-h-[42vh] overflow-y-auto rounded-xl border border-[var(--line)]">
          <ul className="divide-hair divide-y bg-[var(--surface)]">
            {items.map((p) => {
              const { words, hook } = wordCount(p);
              const confirm = confirmId === p.record_id;
              const copied = copiedId === p.record_id;
              return (
                <li key={p.record_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(p.record_id)}
                    className={`w-full px-3 py-2.5 text-left transition ${
                      selectedId === p.record_id ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--surface-2)]"
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Thumb rec={p} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-xs font-medium text-[var(--ink)]">
                            {p.user_query || p.topic || p.record_id}
                          </span>
                          <StatusBadge status={p.record_status} />
                        </div>
                        <div className="mt-0.5 flex items-center gap-2">
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
                          <span className="truncate text-xs text-[var(--faint)]" title={hook}>
                            {hook}
                            {hook.length >= 90 ? "…" : ""}
                          </span>
                        </div>
                        <div className="mt-0.5 flex items-center gap-2">
                          <span className="text-[10px]" style={{ color: "var(--faint)" }}>
                            {formatLocalTime(p.created_at)}
                          </span>
                          <span className="text-[10px]" style={{ color: "var(--faint)" }}>
                            · {words} words
                          </span>
                        </div>
                      </div>
                    </div>
                  </button>

                  <div
                    className="flex flex-wrap items-center gap-0.5 border-t px-2.5 py-1.5"
                    style={{ borderTopColor: "var(--line)", background: "var(--surface-1)" }}
                  >
                    <button
                      type="button"
                      onClick={() => onSelect(p.record_id)}
                      className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-[var(--muted)] transition hover:bg-[var(--surface-2)] hover:text-[var(--accent)]"
                    >
                      <PencilIcon /> Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => void copyPost(p)}
                      className={`flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition hover:bg-[var(--surface-2)] ${
                        copied ? "text-[var(--accent)]" : "text-[var(--muted)] hover:text-[var(--accent)]"
                      }`}
                    >
                      {copied ? <span className="text-xs">✓</span> : <CopyIcon />}
                      {copied ? "Copied" : "Copy"}
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        void api
                          .duplicatePost(p.record_id)
                          .then((rec) => {
                            onDuplicate(rec);
                            onToast("Draft created from this post", "success", {
                              label: "Undo",
                              onClick: () => {
                                void api.deletePost(rec.record_id).catch(() => {});
                                setItems((prev) => prev.filter((x) => x.record_id !== rec.record_id));
                              },
                            });
                          })
                          .catch((err: Error) => onToast(err.message, "error"))
                      }
                      className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-[var(--muted)] transition hover:bg-[var(--surface-2)] hover:text-[var(--accent)]"
                    >
                      <DuplicateIcon /> Duplicate
                    </button>
                    <button
                      type="button"
                      onClick={() => void deletePost(p)}
                      title={confirm ? "Tap again to delete" : "Delete post"}
                      className={`flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition ${
                        confirm
                          ? "bg-[var(--danger)] text-white"
                          : "text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--danger)]"
                      }`}
                    >
                      <TrashIcon /> {confirm ? "Sure?" : "Delete"}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {hasMore && (
        <button
          type="button"
          onClick={loadMore}
          disabled={loading}
          className="btn-secondary w-full py-2 text-xs"
        >
          {loading ? "Loading…" : `Load more (${total - items.length} remaining)`}
        </button>
      )}
    </div>
  );
}