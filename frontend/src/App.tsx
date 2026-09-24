import { useCallback, useEffect, useState } from "react";
import ApprovalPanel from "./components/ApprovalPanel";
import DevicePreview, { type DeviceId } from "./components/DevicePreview";
import EditSuggestions from "./components/EditSuggestions";
import FilterBar from "./components/FilterBar";
import HashtagDisplay from "./components/HashtagDisplay";
import ImagePreview from "./components/ImagePreview";
import LoginScreen from "./components/LoginScreen";
import PostEditor from "./components/PostEditor";
import PostGenerator from "./components/PostGenerator";
import PostHistory from "./components/PostHistory";
import PostPreview from "./components/PostPreview";
import StatusBadge from "./components/StatusBadge";
import ThemeToggle from "./components/ThemeToggle";
import { useReveal } from "./hooks/useReveal";
import { api } from "./services/api";
import { logout, me } from "./services/auth";
import type { FormattingPrefs, PostFilters, PostListResponse, PostRecord, User } from "./types";
import { DEFAULT_FORMATTING } from "./types";
import { humanizeEvent, parseHashtagLine, timeAgo } from "./utils/format";

const VIEW_KEY = "li_agent_view";

type ToastKind = "success" | "error";
type Toast = { id: number; kind: ToastKind; text: string };
let toastSeq = 0;

type SavedView = {
  rid: string | null;
  query: string;
  filters: PostFilters;
  language: string;
  formatting: FormattingPrefs;
};

function normalizeFormatting(f: unknown): FormattingPrefs {
  const d = DEFAULT_FORMATTING;
  if (!f || typeof f !== "object") return { ...d };
  const o = f as Record<string, unknown>;
  return {
    emojis: typeof o.emojis === "boolean" ? o.emojis : d.emojis,
    bullets: typeof o.bullets === "boolean" ? o.bullets : d.bullets,
    bold_keywords: typeof o.bold_keywords === "boolean" ? o.bold_keywords : d.bold_keywords,
    short_paragraphs: typeof o.short_paragraphs === "boolean" ? o.short_paragraphs : d.short_paragraphs,
    practitioner_story:
      typeof o.practitioner_story === "boolean" ? o.practitioner_story : d.practitioner_story,
    discussion_cta: typeof o.discussion_cta === "boolean" ? o.discussion_cta : d.discussion_cta,
    word_target: typeof o.word_target === "number" && Number.isFinite(o.word_target) ? o.word_target : d.word_target,
  };
}

function loadSavedView(): SavedView {
  try {
    const raw = JSON.parse(localStorage.getItem(VIEW_KEY) ?? "null");
    if (!raw || typeof raw !== "object") {
      return { rid: null, query: "", filters: {}, language: "English", formatting: { ...DEFAULT_FORMATTING } };
    }
    return {
      rid: raw.rid ? String(raw.rid) : null,
      query: typeof raw.query === "string" ? raw.query : "",
      filters:
        raw.filters && typeof raw.filters === "object"
          ? {
              priority: typeof raw.filters.priority === "string" ? raw.filters.priority : undefined,
              post_type: typeof raw.filters.post_type === "string" ? raw.filters.post_type : undefined,
              status: typeof raw.filters.status === "string" ? raw.filters.status : undefined,
            }
          : {},
      language: typeof raw.language === "string" && raw.language ? raw.language : "English",
      formatting: normalizeFormatting(raw.formatting),
    };
  } catch {
    return { rid: null, query: "", filters: {}, language: "English", formatting: { ...DEFAULT_FORMATTING } };
  }
}

type SessionState =
  | { phase: "booting"; user: null }
  | { phase: "anon"; user: null }
  | { phase: "authed"; user: User };

type RailMode = "create" | "history";

export default function App() {
  const [session, setSessionState] = useState<SessionState>({ phase: "booting", user: null });
  const [rail, setRail] = useState<RailMode>("create");
  const [device, setDevice] = useState<DeviceId>("desktop");
  const [query, setQuery] = useState("");
  const [generating, setGenerating] = useState(false);
  const [active, setActive] = useState<PostRecord | null>(null);
  const [edits, setEdits] = useState({ draft: "", tags: [] as string[], dirty: false });
  const [tagCandidates, setTagCandidates] = useState<string[]>([]);
  const [history, setHistory] = useState<PostListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filters, setFilters] = useState<PostFilters>({});
  const [language, setLanguage] = useState("English");
  const [formatting, setFormatting] = useState<FormattingPrefs>({ ...DEFAULT_FORMATTING });
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [onboard, setOnboard] = useState(() => {
    try {
      return localStorage.getItem("li_onboard_done") !== "1";
    } catch {
      return true;
    }
  });

  const dismissOnboard = useCallback(() => {
    setOnboard(false);
    try {
      localStorage.setItem("li_onboard_done", "1");
    } catch {
      /* non-fatal */
    }
  }, []);

  const notify = useCallback((text: string, kind: ToastKind = "success") => {
    const id = ++toastSeq;
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3600);
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      const data = await api.list(100, 0, filters);
      setHistory(data);
    } catch {
      /* non-fatal */
    }
  }, [filters]);

  const selectRecord = useCallback((rec: PostRecord | null) => {
    setActive(rec);
    setEdits({
      draft: rec?.final_post ?? rec?.generated_post ?? "",
      tags: rec?.hashtags ?? [],
      dirty: false,
    });
    setTagCandidates(
      rec ? Array.from(new Set([...parseHashtagLine(rec.generated_post ?? ""), ...(rec.hashtags ?? [])])) : [],
    );
    setError(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const user = await me();
      if (cancelled) return;
      setSessionState(user ? { phase: "authed", user } : { phase: "anon", user: null });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (session.phase !== "authed") return;
    localStorage.setItem(
      VIEW_KEY,
      JSON.stringify({ rid: active?.record_id ?? null, query, filters, language, formatting }),
    );
  }, [session.phase, active, query, filters, language, formatting]);

  useEffect(() => {
    if (session.phase !== "authed") return;
    const saved = loadSavedView();
    if (saved.rid) {
      api
        .get(saved.rid)
        .then(selectRecord)
        .catch(() => undefined);
    }
    if (saved.query) setQuery(saved.query);
    if (saved.language) setLanguage(saved.language);
    setFormatting(saved.formatting);
    if (Object.keys(saved.filters).some((k) => !!(saved.filters as Record<string, string>)[k])) {
      setFilters(saved.filters);
    }
    void api.list(100, 0, saved.filters).then(setHistory).catch(() => undefined);
  }, [session.phase, selectRecord]);

  const handleAuthed = useCallback(
    (user: User) => {
      setSessionState({ phase: "authed", user });
      void loadHistory();
    },
    [loadHistory],
  );

  const handleSignOut = async () => {
    await logout();
    setSessionState({ phase: "anon", user: null });
    setActive(null);
    setHistory(null);
  };

  useReveal(session.phase === "authed" ? active?.record_id ?? "authed" : session.phase);

  const runAction = async (
    action: () => Promise<PostRecord>,
    successMsg?: string | ((rec: PostRecord) => string),
    embed = true,
  ) => {
    setBusy(true);
    setError(null);
    try {
      const rec = await action();
      if (embed) selectRecord(rec);
      else setActive(rec);
      await loadHistory();
      notify(typeof successMsg === "function" ? successMsg(rec) : successMsg ?? "Done");
      return rec;
    } catch (e) {
      const message = e instanceof Error ? e.message : "Request failed";
      setError(message);
      notify(message, "error");
      return null;
    } finally {
      setBusy(false);
    }
  };

  const handleGenerate = (topic?: string) => {
    const raw = (topic ?? query).trim();
    if (!raw || generating) return;
    if (!topic) setQuery("");
    setGenerating(true);
    void api
      .generate(raw, filters, language, formatting)
      .then((rec) => {
        setQuery("");
        selectRecord(rec);
        void loadHistory();
        notify("Draft ready — review it in step 1");
      })
      .catch((e: Error) => {
        setError(e.message);
        notify(e.message, "error");
      })
      .finally(() => setGenerating(false));
  };

  const handleSave = () => {
    if (!active) return;
    void runAction(
      async () => {
        const rec = await api.update(active.record_id, edits.draft, edits.tags);
        setEdits((e) => ({ ...e, dirty: false }));
        return rec;
      },
      (rec) => (rec.record_status === "PUBLISHED" ? "Revision saved" : "Changes saved"),
    );
  };

  const approve = (approved: boolean) => {
    if (!active) return;
    if (!approved && !window.confirm("Reject this post? It will be marked for discard.")) return;
    void runAction(
      async () => {
        const rec = await api.approve(active.record_id, approved);
        if (approved && rec.record_status === "PUBLISHED") setEdits((e) => ({ ...e, dirty: false }));
        return rec;
      },
      approved
        ? (rec) => (rec.record_status === "PUBLISHED" ? "Published to LinkedIn ✓" : "Approved — ready to publish")
        : "Post rejected",
    );
  };

  const publish = () => {
    if (!active) return;
    if (active.record_status === "PUBLISHED" && !window.confirm("Publish a new LinkedIn post from this copy?")) {
      return;
    }
    void runAction(
      async () => {
        const rec = await api.publish(active.record_id);
        if (rec.publishing_status === "PUBLISHED") setEdits((e) => ({ ...e, dirty: false }));
        return rec;
      },
      (rec) => (rec.publishing_status === "PUBLISHED" ? "Published to LinkedIn ✓" : "Publish finished"),
    );
  };

  const regenImage = () => {
    if (!active) return;
    void runAction(() => api.regenerateImage(active.record_id));
  };

  if (session.phase !== "authed") {
    if (session.phase === "booting") {
      return (
        <div className="flex min-h-screen items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--line)] border-t-[var(--accent)]" />
        </div>
      );
    }
    return <LoginScreen onAuthed={handleAuthed} />;
  }

  const user = session.user;
  const selected = active;
  const published = selected?.record_status === "PUBLISHED";

  const dock: { label: string; disabled: boolean; onClick: (() => void) | undefined } = (() => {
    if (generating) return { label: "Generating…", disabled: true, onClick: undefined };
    if (!selected) {
      if (!query.trim()) return { label: "Type a topic above", disabled: true, onClick: undefined };
      return { label: "✦ Generate post", disabled: false, onClick: () => handleGenerate() };
    }
    if (published && edits.dirty) return { label: "Save revision", disabled: busy, onClick: handleSave };
    if (published) return { label: "Republish revision", disabled: busy, onClick: publish };
    if (edits.dirty) return { label: "Save edits", disabled: busy, onClick: handleSave };
    if (selected.approval_status === "APPROVED") {
      return { label: "Publish to LinkedIn", disabled: busy, onClick: publish };
    }
    return { label: "✓ Approve & publish", disabled: busy, onClick: () => approve(true) };
  })();

  return (
    <div className="min-h-screen">
      {/* ─── top bar ─────────────────────────────────────────── */}
      <header className="u-header sticky top-0 z-40 border-b" style={{ borderColor: "var(--line)" }}>
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-3 py-2.5 sm:px-4">
          <div className="flex min-w-0 items-center gap-3">
            <img src="/favicon.png" alt="" className="h-9 w-9 shrink-0 rounded-lg" />
            <div className="min-w-0">
              <h1 className="truncate text-sm font-bold leading-tight" style={{ color: "var(--ink)" }}>
                PostCraft
              </h1>
              <p
                className="hidden font-mono text-[10px] uppercase tracking-[0.12em] sm:block"
                style={{ color: "var(--faint)" }}
              >
                Generate · Review · Approve · Publish
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            <ThemeToggle />
            <div
              className="flex items-center gap-2 rounded-full border py-1 pl-1 pr-3"
              style={{ borderColor: "var(--line-2)" }}
            >
              {user.picture_url ? (
                <img src={user.picture_url} alt={user.name} className="h-7 w-7 rounded-full" />
              ) : (
                <div
                  className="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white"
                  style={{ background: "linear-gradient(135deg,#2f6fed,#7b2ff7)" }}
                >
                  {user.name
                    .split(" ")
                    .map((w) => w[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase()}
                </div>
              )}
              <span className="hidden max-w-[120px] truncate text-xs font-semibold sm:block" style={{ color: "var(--ink)" }}>
                {user.name}
              </span>
              <button
                type="button"
                onClick={handleSignOut}
                className="text-[11px] font-medium transition"
                style={{ color: "var(--faint)" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--bad)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--faint)")}
              >
                Sign out
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-3 pb-28 pt-5 sm:px-4 sm:pb-32 sm:pt-6 lg:py-6">
        <div className="grid gap-6 lg:grid-cols-[minmax(300px,340px)_1fr] lg:items-start">
          {/* ─── rail: single tab widget switches Create ⇄ History ── */}
          <div className="order-2 space-y-3 lg:order-none lg:sticky lg:top-16">
            <div
              role="tablist"
              aria-label="Workspace"
              className="flex items-center gap-1 rounded-xl border p-1"
              style={{ borderColor: "var(--line-2)" }}
            >
              {(
                [
                  { id: "create", label: "Create" },
                  { id: "history", label: "History" },
                ] as Array<{ id: RailMode; label: string }>
              ).map((t) => {
                const active = rail === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setRail(t.id)}
                    className="flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold transition"
                    style={{
                      background: active ? "var(--accent-soft)" : "transparent",
                      color: active ? "var(--accent-ink)" : "var(--faint)",
                    }}
                  >
                    {t.id === "create" ? "＋" : "☰"} {t.label}
                    {t.id === "history" && history && (
                      <span
                        className="rounded-full px-1.5 text-[10px]"
                        style={{ background: "var(--surface-2)", color: "var(--muted)" }}
                      >
                        {history.items.length}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {rail === "create" ? (
              <PostGenerator
                query={query}
                setQuery={setQuery}
                language={language}
                setLanguage={setLanguage}
                formatting={formatting}
                setFormatting={setFormatting}
                generating={generating}
                error={generating ? null : error}
                onGenerate={handleGenerate}
              />
            ) : (
              <div className="card rv space-y-3 p-4">
                <FilterBar
                  filters={filters}
                  onChange={(f) => {
                    setFilters(f);
                    void api.list(100, 0, f).then(setHistory).catch(() => undefined);
                  }}
                />
                <PostHistory
                  data={history}
                  loading={false}
                  selectedId={selected?.record_id ?? null}
                  onSelect={async (id) => {
                    setBusy(true);
                    try {
                      const rec = await api.get(id);
                      selectRecord(rec);
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Failed to load post");
                    } finally {
                      setBusy(false);
                    }
                  }}
                  onRefresh={() => void loadHistory()}
                />
              </div>
            )}
          </div>

          {/* ─── workspace: categorized review flow ─────────── */}
          <div className="relative order-1 min-w-0 space-y-5 lg:order-none">
            {generating && (
              <div
                className="pointer-events-none absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 rounded-2xl p-8 text-center"
                style={{
                  background: "color-mix(in srgb, var(--bg) 55%, transparent)",
                  backdropFilter: "blur(6px)",
                }}
                role="status"
                aria-live="polite"
              >
                <div
                  className="h-9 w-9 animate-spin rounded-full border-2 border-t-2"
                  style={{ borderColor: "var(--line-strong)", borderTopColor: "var(--accent)" }}
                />
                <p className="text-sm font-bold" style={{ color: "var(--ink)" }}>
                  Generating your post…
                </p>
                <p className="hint">Draft, quality check, and visual are being prepared — you'll review it here.</p>
              </div>
            )}
            {error && (
              <div
                className="rounded-xl border px-4 py-2.5 text-sm font-medium"
                style={{ borderColor: "var(--bad-soft)", background: "var(--bad-soft)", color: "var(--bad)" }}
              >
                {error}
              </div>
            )}

            {!selected && onboard ? (
              <section className="section-card rv">
                <div className="mb-3 flex items-start justify-between gap-3">
                  <header className="section-head !mb-0">
                    <span className="section-step">i</span>
                    <div>
                      <h2 className="text-sm font-bold" style={{ color: "var(--ink)" }}>
                        How it works
                      </h2>
                      <p className="hint">Four simple steps — you can stop at any point.</p>
                    </div>
                  </header>
                  <button type="button" onClick={dismissOnboard} className="btn-ghost shrink-0 !px-2 !py-1 text-xs" aria-label="Dismiss guide">
                    ✕ Skip guide
                  </button>
                </div>
                <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {[
                    ["1 · Create", "Type or tap a topic and choose a language, then generate."],
                    ["2 · Review", "Read the draft, edit the copy, try AI suggestions."],
                    ["3 · Check", "Confirm the image and the automatic quality pass."],
                    ["4 · Publish", "Approve, then publish — or republish a revision."],
                  ].map(([t, d]) => (
                    <li key={t} className="rounded-xl p-3" style={{ background: "var(--surface-2)" }}>
                      <p className="text-xs font-bold" style={{ color: "var(--accent)" }}>
                        {t}
                      </p>
                      <p className="mt-0.5 text-[11px] leading-relaxed" style={{ color: "var(--muted)" }}>
                        {d}
                      </p>
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}

            {!selected ? null : (
              <>
                {/* post header */}
                <div className="card rv flex flex-wrap items-center gap-2 p-4">
                  <span
                    className="rounded-full border px-2.5 py-1 font-mono text-[11px]"
                    style={{ borderColor: "var(--line-2)", color: "var(--muted)" }}
                    title={selected.record_id}
                  >
                    ↻ {timeAgo(selected.created_at)}
                  </span>
                  <StatusBadge status={selected.record_status} />
                  <StatusBadge status={selected.validation_status || "UNVALIDATED"} />
                  {selected.linkedin_post_id && <StatusBadge status={selected.publishing_status} />}
                  <span
                    className={`tag ${
                      selected.priority === "High"
                        ? "tag--peach"
                        : selected.priority === "Low"
                          ? "tag--slate"
                          : "tag--butter"
                    }`}
                  >
                    {selected.priority}
                  </span>
                  <span className="tag tag--lavender">{selected.post_type}</span>
                  <span className="tag tag--sky">🌐 {selected.language || "English"}</span>
                  {published && <span className="tag tag--mint">Live on LinkedIn</span>}
                </div>

                {/* 01 · Review & edit */}
                <section className="section-card rv">
                  <header className="section-head">
                    <span className="section-step">1</span>
                    <div>
                      <h2 className="text-sm font-bold" style={{ color: "var(--ink)" }}>
                        Review &amp; edit
                      </h2>
                      <p className="hint">Preview on phone, tablet or desktop, then refine the copy.</p>
                    </div>
                  </header>
                  <div className="grid gap-5 xl:grid-cols-2">
                    <div>
<DevicePreview device={device} onChange={setDevice}>
  <PostPreview
    record={selected}
    user={user}
    variant={device === "desktop" ? "desktop" : "mobile"}
  />
</DevicePreview>
                    </div>
                    <div className="space-y-4">
                      <div>
                        <p className="label mb-1.5">Post editor</p>
                        <PostEditor
                          text={edits.draft}
                          onChange={(d) => setEdits((e) => ({ ...e, draft: d, dirty: true }))}
                        />
                        <p className="hint mt-1.5" style={{ color: "var(--faint)" }}>
                          **Bold** and • bullets read clearly here; LinkedIn shows published posts as plain text.
                        </p>
                      </div>
                      <EditSuggestions
                        recordId={selected.record_id}
                        formatting={formatting}
                        onApply={(draft) => {
                          setEdits((e) => ({ ...e, draft, dirty: true }));
                          notify("Suggested version applied — review & save", "success");
                        }}
                        onReworked={async (rec) => {
                          selectRecord(rec);
                          await loadHistory();
                        }}
                      />
                    </div>
                  </div>
                </section>

                {/* 02 · Visual */}
                <section className="section-card rv">
                  <header className="section-head">
                    <span className="section-step">2</span>
                    <div>
                      <h2 className="text-sm font-bold" style={{ color: "var(--ink)" }}>
                        Visual
                      </h2>
                      <p className="hint">On-topic image in the selected language — regenerate anytime.</p>
                    </div>
                  </header>
                  <ImagePreview
                    url={selected.image_url ?? ""}
                    prompt={selected.image_prompt}
                    busy={busy}
                    onRegenerate={regenImage}
                  />
                </section>

                {/* 03 · Quality gate */}
                <section className="section-card rv">
                  <header className="section-head">
                    <span className="section-step">3</span>
                    <div>
                      <h2 className="text-sm font-bold" style={{ color: "var(--ink)" }}>
                        Quality gate
                      </h2>
                      <p className="hint">Automatic validation before anything goes live.</p>
                    </div>
                  </header>
                  <div className="space-y-2 rounded-xl p-4 text-sm" style={{ background: "var(--surface-2)" }}>
                    <div className="flex items-center justify-between">
                      <span style={{ color: "var(--faint)" }}>Validation</span>
                      <span className={`font-bold ${selected.validation_result?.valid ? "" : ""}`} style={{ color: selected.validation_result?.valid ? "var(--ok)" : "var(--bad)" }}>
                        {selected.validation_result?.valid ? "PASSED" : "FAILED"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span style={{ color: "var(--faint)" }}>Quality score</span>
                      <span className="font-bold" style={{ color: "var(--accent)" }}>
                        {Math.round((selected.validation_result?.quality_score ?? 0) * 100)}%
                      </span>
                    </div>
                    {!!(selected.validation_result?.issues?.length) && (
                      <div className="rounded-lg p-2 text-xs" style={{ background: "var(--bad-soft)", color: "var(--bad)" }}>
                        <div className="font-semibold">Issues:</div>
                        <ul className="mt-1 list-disc space-y-0.5 pl-4">
                          {selected.validation_result.issues.map((i) => (
                            <li key={i}>{i}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {!!(selected.validation_result?.suggestions?.length) && (
                      <div className="rounded-lg p-2 text-xs" style={{ background: "var(--sky-soft)", color: "var(--sky)" }}>
                        <div className="font-semibold">Suggestions:</div>
                        <ul className="mt-1 list-disc space-y-0.5 pl-4">
                          {selected.validation_result.suggestions.map((i) => (
                            <li key={i}>{i}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <div className="flex items-center justify-between text-xs">
                      <span style={{ color: "var(--faint)" }}>Audience</span>
                      <span className="truncate pl-3" style={{ color: "var(--muted)" }}>
                        {selected.audience || "—"}
                      </span>
                    </div>
                  </div>
                </section>

                {/* 04 · Hashtags & publish */}
                <section className="section-card rv">
                  <header className="section-head">
                    <span className="section-step">4</span>
                    <div>
                      <h2 className="text-sm font-bold" style={{ color: "var(--ink)" }}>
                        Hashtags &amp; publish
                      </h2>
                      <p className="hint">
                        {published ? "Adjust tags, then republish a revision as a new post." : "Finetune tags and ship the approved version."}
                      </p>
                    </div>
                  </header>
                  <div className="space-y-4">
                    <HashtagDisplay
                      hashtags={edits.tags}
                      candidates={tagCandidates}
                      editing
                      onChange={(tags) => setEdits((e) => ({ ...e, tags, dirty: true }))}
                    />
                    <ApprovalPanel
                      record={selected}
                      busy={busy}
                      dirty={edits.dirty}
                      saving={busy}
                      onSave={handleSave}
                      onApprove={() => approve(true)}
                      onReject={() => approve(false)}
                      onPublish={publish}
                    />
                    <details className="group">
                      <summary
                        className="flex cursor-pointer select-none items-center gap-1.5 text-xs font-semibold transition"
                        style={{ color: "var(--muted)" }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = "var(--ink)")}
                        onMouseLeave={(e) => (e.currentTarget.style.color = "var(--muted)")}
                      >
                        <span
                          className="inline-block transition-transform group-open:rotate-90"
                          style={{ color: "var(--faint)" }}
                        >
                          ›
                        </span>
                        Activity &amp; revisions ({selected.history.length})
                      </summary>
                      <ul className="mt-2 space-y-1.5">
                        {selected.history.length === 0 && (
                          <li className="rounded-lg px-3 py-2 text-xs" style={{ background: "var(--surface-2)", color: "var(--faint)" }}>
                            Nothing recorded yet.
                          </li>
                        )}
                        {[...selected.history].reverse().map((h, i) => (
                          <li
                            key={`${h.event}-${i}`}
                            className="flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-xs"
                            style={{ background: "var(--surface-2)", color: "var(--muted)" }}
                          >
                            <span>{humanizeEvent(h.event)}</span>
                            <span className="shrink-0" style={{ color: "var(--faint)" }}>
                              {timeAgo(h.at)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </details>
                  </div>
                </section>
              </>
            )}
          </div>
        </div>
      </main>

      {/* ─── mobile action dock ────────────────────────────── */}
      <div
        className="fixed inset-x-0 bottom-0 z-40 border-t px-3 py-3 lg:hidden"
        style={{ borderColor: "var(--line)", background: "var(--header-bg)", backdropFilter: "blur(8px)" }}
      >
        <div className="mx-auto flex max-w-7xl items-center gap-2">
          {selected && !published && !edits.dirty && selected.approval_status !== "APPROVED" && (
            <button type="button" onClick={() => approve(false)} disabled={busy || generating} className="btn-danger shrink-0 px-3 py-3 text-sm" aria-label="Reject post">
              ✕
            </button>
          )}
          <button
            type="button"
            onClick={dock.onClick}
            disabled={dock.disabled}
            className="btn-primary flex-1 py-3"
            aria-label={dock.label}
          >
            {dock.label}
          </button>
        </div>
      </div>

      {/* ─── toasts ────────────────────────────────────────── */}
      <div className="pointer-events-none fixed right-3 top-16 z-[60] flex w-[calc(100%-1.5rem)] max-w-sm flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="toast-in pointer-events-auto flex items-start gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium shadow-lg"
            style={{
              borderColor: t.kind === "success" ? "var(--ok-soft)" : "var(--bad-soft)",
              background: t.kind === "success" ? "var(--ok-soft)" : "var(--bad-soft)",
              color: t.kind === "success" ? "var(--ok)" : "var(--bad)",
            }}
          >
            <span className="shrink-0 font-bold">{t.kind === "success" ? "✓" : "✕"}</span>
            <span className="min-w-0 flex-1">{t.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}