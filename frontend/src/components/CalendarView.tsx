import { useEffect, useMemo, useState } from "react";
import type { PostFilters, PostRecord } from "../types";
import { api } from "../services/api";
import { formatLocalTime } from "../utils/format";
import Skeleton from "./Skeleton";

interface Props {
  selectedId: string | null;
  onSelect: (id: string) => void;
  onToast: (text: string, kind?: "success" | "error") => void;
}

const STATUS_CLASS: Record<string, string> = {
  PUBLISHED: "bg-[#0f8a6d]",
  SCHEDULED: "bg-[#6a4fd1]",
  FAILED: "bg-[#c62b3c]",
};

function calKey(rec: PostRecord): string {
  const iso = rec.scheduled_at || rec.published_at || rec.created_at;
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

export default function CalendarView({ selectedId, onSelect, onToast }: Props) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const [cursor, setCursor] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));
  const [day, setDay] = useState<string | null>(null);
  const [posts, setPosts] = useState<PostRecord[]>([]);
  const [loading, setLoading] = useState(false);

  const from = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}-01`;
  const to = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}-${String(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate()).padStart(2, "0")}`;

  useEffect(() => {
    setLoading(true);
    const filters: PostFilters = { from_date: from, to_date: to, sort: "oldest" };
    void api
      .list(1000, 0, filters)
      .then((d) => {
        setPosts(d.items);
        if (day && !d.items.some((r) => calKey(r) === day)) setDay(day);
      })
      .catch(() => onToast("Couldn't load calendar", "error"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [from, to]);

  const byDay = useMemo(() => {
    const m = new Map<string, PostRecord[]>();
    for (const p of posts) {
      const k = calKey(p);
      m.set(k, [...(m.get(k) ?? []), p]);
    }
    return m;
  }, [posts]);

  const grid = useMemo(() => {
    const firstWeekday = (cursor.getDay() + 6) % 7; // Monday-first
    const daysInMonth = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
    const cells: Array<number | null> = [...Array(firstWeekday).fill(null)];
    for (let d = 1; d <= daysInMonth; d += 1) cells.push(d);
    while (cells.length % 7 !== 0) cells.push(null);
    return cells;
  }, [cursor]);

  const dayPosts = day ? (byDay.get(day) ?? []) : [];
  const nav = (delta: number) => {
    setCursor((c) => new Date(c.getFullYear(), c.getMonth() + delta, 1));
    setDay(null);
  };

  const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

  return (
    <div className="card rv space-y-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="label mb-0.5">Calendar</p>
          <h2 className="text-lg font-bold">
            {MONTH_NAMES[cursor.getMonth()]} {cursor.getFullYear()}
          </h2>
        </div>
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => nav(-1)} className="btn-secondary !px-3 !py-2 text-xs" aria-label="Previous month">◀</button>
          <button type="button" onClick={() => { setCursor(new Date(today.getFullYear(), today.getMonth(), 1)); setDay(null); }} className="btn-secondary !px-3 !py-2 text-xs">Today</button>
          <button type="button" onClick={() => nav(1)} className="btn-secondary !px-3 !py-2 text-xs" aria-label="Next month">▶</button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4 text-[11px] font-medium" style={{ color: "var(--faint)" }}>
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-[#0f8a6d]" /> Published</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-[#6a4fd1]" /> Scheduled</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-[#c62b3c]" /> Failed</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--dead)]" /> Draft</span>
        {loading && !posts.length && <span className="inline-flex items-center gap-1"><Skeleton className="h-3 w-14" /> syncing…</span>}
      </div>

      {loading && !posts.length ? (
        <div className="grid grid-cols-7 gap-1.5 pt-1">
          {Array.from({ length: 35 }).map((_, i) => (
            <Skeleton key={i} className="h-14 rounded-xl" />
          ))}
        </div>
      ) : (
      <div className="grid grid-cols-7 gap-1.5">
        {WEEKDAYS.map((w) => (
          <div key={w} className="pb-1 text-center text-[11px] font-semibold" style={{ color: "var(--faint)" }}>
            {w}
          </div>
        ))}
        {grid.map((d, i) => {
          if (d === null) return <div key={`x${i}`} />;
          const key = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
          const dayRecs = byDay.get(key) ?? [];
          const isToday = key === todayKey;
          const isSelected = key === day;
          return (
            <div
              key={key}
              role="button"
              tabIndex={0}
              onClick={() => setDay(isSelected ? null : key)}
              onKeyDown={(e) => { if (e.key === "Enter") setDay(isSelected ? null : key); }}
              className={`min-h-[46px] cursor-pointer rounded-lg border p-1.5 transition ${isSelected ? "ring-2" : "hover:bg-[var(--surface-2)] sm:min-h-[66px] lg:min-h-[86px]"}`}
              style={{
                borderColor: isToday ? "var(--accent)" : "var(--line)",
                background: isSelected ? "var(--accent-soft)" : "var(--surface-1)",
              }}
            >
              <div className="flex items-center justify-between">
                <span className={`text-[11px] font-bold sm:text-xs ${isToday ? "text-[var(--accent)]" : ""}`} style={{ color: isToday ? undefined : "var(--muted)" }}>
                  {d}
                </span>
                {dayRecs.length > 5 && <span className="text-[10px]" style={{ color: "var(--faint)" }}>+{dayRecs.length}</span>}
              </div>
              <div className="mt-1 hidden gap-1 sm:flex sm:flex-col">
                {dayRecs.slice(0, 5).map((r) => (
                  <span key={r.record_id} title={r.user_query || r.topic} className={`block h-2 rounded-full ${STATUS_CLASS[r.record_status] ?? "bg-[var(--dead)]"}`} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
      )}

      <div className="space-y-2">
        <p className="label">{day ? `Posts on ${day}` : "Pick a day to see its posts"}</p>
        {dayPosts.length === 0 ? (
          <p className="rounded-xl border border-dashed p-4 text-center text-xs" style={{ borderColor: "var(--line-strong)", color: "var(--faint)" }}>
            {day ? "Nothing scheduled or published on this day." : "Click any day in the grid."}
          </p>
        ) : (
          <ul className="space-y-1.5">
            {dayPosts.map((r) => (
              <li key={r.record_id}>
                <button
                  type="button"
                  onClick={() => onSelect(r.record_id)}
                  className={`flex w-full flex-wrap items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-xs transition hover:bg-[var(--surface-2)] ${selectedId === r.record_id ? "border-[var(--accent)]" : ""}`}
                  style={{ borderColor: "var(--line-2)" }}
                >
                  <span className={`h-2 w-2 shrink-0 rounded-full ${STATUS_CLASS[r.record_status] ?? "bg-[var(--dead)]"}`} />
                  <span className="min-w-0 flex-1 truncate font-medium" style={{ color: "var(--ink)" }}>
                    {r.user_query || r.topic || r.record_id}
                  </span>
                  <span className="shrink-0 text-[10px]" style={{ color: "var(--faint)" }}>
                    {formatLocalTime(r.scheduled_at || r.published_at || r.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}