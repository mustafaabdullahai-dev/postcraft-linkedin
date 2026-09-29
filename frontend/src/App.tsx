import { useCallback, useEffect, useState } from "react";
import ApprovalPanel from "./components/ApprovalPanel";
import CalendarView from "./components/CalendarView";
import CommandMenu, { type PaletteCommand } from "./components/CommandMenu";
import DevicePreview, { type DeviceId } from "./components/DevicePreview";
import EditSuggestions from "./components/EditSuggestions";
import FilterBar from "./components/FilterBar";
import GeneratingOverlay from "./components/GeneratingOverlay";
import HashtagDisplay from "./components/HashtagDisplay";
import ImagePreview from "./components/ImagePreview";
import LoginScreen from "./components/LoginScreen";
import PostEditor from "./components/PostEditor";
import PostGenerator from "./components/PostGenerator";
import GuidelinesPanel from "./components/GuidelinesPanel";
import MobileMenu from "./components/MobileMenu";
import PostHistory from "./components/PostHistory";
import PostPreview from "./components/PostPreview";
import StatusBadge from "./components/StatusBadge";
import ThemeToggle from "./components/ThemeToggle";
import SectionNav, { useActiveSection, type SectionRef } from "./components/SectionNav";
import VariationPicker from "./components/VariationPicker";
import { useMediaQuery } from "./hooks/useMediaQuery";
import { useReveal } from "./hooks/useReveal";
import { api } from "./services/api";
import { exchangeAuthCode, logout, me } from "./services/auth";
import type { FormattingPrefs, GuidelineGroup, PostFilters, PostRecord, StatusCounts, User, VoiceProfile } from "./types";
import { DEFAULT_FORMATTING } from "./types";
import { formatLocalTime, humanizeEvent, parseHashtagLine, timeAgo } from "./utils/format";
import { composeHashtagLine, toLinkedInText } from "./utils/linkedin";
import SubTabs from "./components/SubTabs";

const VIEW_KEY = "li_agent_view";

const REVIEW_SECTIONS: SectionRef[] = [
  { id: "sec-review", step: "1", label: "Review & edit" },
  { id: "sec-visual", step: "2", label: "Visual" },
  { id: "sec-quality", step: "3", label: "Quality gate" },
  { id: "sec-hashtags", step: "4", label: "Hashtags & publish" },
];

type ToastKind = "success" | "error";
type ToastAction = { label: string; onClick: () => void };
type Toast = { id: number; kind: ToastKind; text: string; action?: ToastAction };
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

type RailMode = "create" | "history" | "calendar";

export default function App() {
  const [session, setSessionState] = useState<SessionState>({ phase: "booting", user: null });
  const [rail, setRail] = useState<RailMode>("create");
  const [histSub, setHistSub] = useState<"posts" | "filters" | "stats">("posts");
  const [histCounts, setHistCounts] = useState<StatusCounts | null>(null);
  const [device, setDevice] = useState<DeviceId>("desktop");
  const [query, setQuery] = useState("");
  const [generating, setGenerating] = useState(false);
  const [active, setActive] = useState<PostRecord | null>(null);
  const [edits, setEdits] = useState({ draft: "", tags: [] as string[], dirty: false });
  const [tagCandidates, setTagCandidates] = useState<string[]>([]);
  const [historyTick, setHistoryTick] = useState(0);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filters, setFilters] = useState<PostFilters>({});
  const [language, setLanguage] = useState("English");
  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [variations, setVariations] = useState(1);
  const [variants, setVariants] = useState<PostRecord[] | null>(null);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [formatting, setFormatting] = useState<FormattingPrefs>({ ...DEFAULT_FORMATTING });
  const [includeImage, setIncludeImage] = useState(true);
  const [guidelinesOpen, setGuidelinesOpen] = useState(false);
  const [guidelines, setGuidelines] = useState<GuidelineGroup[] | null>(null);
  const [guidelinesSource, setGuidelinesSource] = useState<string | undefined>(undefined);
  const [guidelinesDisclaimer, setGuidelinesDisclaimer] = useState<string | undefined>(undefined);
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

  const notify = useCallback((text: string, kind: ToastKind = "success", action?: ToastAction) => {
    const id = ++toastSeq;
    setToasts((t) => [...t.slice(-3), { id, kind, text, action }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3600);
  }, []);

  const bumpHistory = useCallback(() => setHistoryTick((t) => t + 1), []);

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
      await exchangeAuthCode();
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
    try {
      localStorage.setItem(
        VIEW_KEY,
        JSON.stringify({ rid: active?.record_id ?? null, query, filters, language, formatting }),
      );
    } catch {
      /* never let a persistence hiccup break the app */
    }
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
    bumpHistory();
  }, [session.phase, selectRecord, bumpHistory]);

  useEffect(() => {
    if (session.phase !== "authed") return;
    let cancelled = false;
    void api
      .voiceProfiles
      .list()
      .then((list) => {
        if (cancelled) return;
        setVoices(list);
        setVoiceId((current) => list.some((v) => v.voice_id === current) ? current : "");
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [session.phase]);

  const handleAuthed = useCallback(
    (user: User) => {
      setSessionState({ phase: "authed", user });
      bumpHistory();
    },
    [bumpHistory],
  );

  const handleSignOut = async () => {
    await logout();
    setSessionState({ phase: "anon", user: null });
    setActive(null);
  };

  useEffect(() => {
    if (session.phase !== "authed") return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen((s) => !s);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [session.phase]);

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
      bumpHistory();
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
    setVariants(null);
    setGenerating(true);
    const done = (work: Promise<unknown>) =>
      work.catch((e: Error) => {
        setError(e.message);
        notify(e.message, "error");
      });
    if (variations > 1) {
      done(
        api
          .batchGenerate(raw, variations, filters, language, formatting, voiceId || undefined, includeImage)
          .then(async ({ items }) => {
            setQuery("");
            setGenerating(false);
            const ok = items.filter((r) => r.record_status !== "FAILED");
            if (ok.length === 0) {
              setError("Generation failed — please retry.");
              notify("Generation failed — please retry.", "error");
              return;
            }
            setVariants(ok);
            bumpHistory();
            notify(`${ok.length} drafts ready — pick your favourite`);
          })
          .finally(() => setGenerating(false)),
      );
      return;
    }
    void api
      .generate(raw, filters, language, formatting, voiceId || undefined, includeImage)
      .then((rec) => {
        setQuery("");
        selectRecord(rec);
        bumpHistory();
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

  const approve = (approved: boolean, scheduledAt?: string) => {
    if (!active) return;
    if (!approved && !window.confirm("Reject this post? It will be marked for discard.")) return;
    void runAction(
      async () => {
        const rec = await api.approve(active.record_id, approved, scheduledAt);
        if (approved && rec.record_status === "PUBLISHED") setEdits((e) => ({ ...e, dirty: false }));
        return rec;
      },
      approved
        ? (rec) =>
            rec.record_status === "SCHEDULED"
              ? `Scheduled for ${formatLocalTime(rec.scheduled_at ?? "")}`
              : "Published to LinkedIn ✓"
        : "Post rejected",
    );
  };

  const publish = (revision = false) => {
    const rev = revision === true;
    if (!active) return;
    if (active.record_status === "PUBLISHED" && !window.confirm("Publish a new LinkedIn post from this copy?")) {
      return;
    }
    void runAction(
      async () => {
        const rec = await api.publish(active.record_id, rev);
        if (rec.publishing_status === "PUBLISHED") setEdits((e) => ({ ...e, dirty: false }));
        return rec;
      },
      (rec) => (rec.publishing_status === "PUBLISHED" ? "Published to LinkedIn ✓" : "Publish finished"),
    );
  };

  const regenImage = (prompt?: string) => {
    if (!active) return;
    void runAction(() => api.regenerateImage(active.record_id, prompt));
  };

  const uploadImage = (file: File) => {
    if (!active) return;
    void runAction(() => api.uploadImage(active.record_id, file), "Image attached");
  };

  const { activeId: reviewSectionId, goTo: goToReviewSection } = useActiveSection(REVIEW_SECTIONS);
  const isDesktop = useMediaQuery("(min-width: 1024px)");

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

  const paletteCommands: PaletteCommand[] = [
    { id: "create", icon: "＋", title: "Create a post", hint: "Type a topic, pick a voice, generate", run: () => setRail("create") },
    { id: "history", icon: "☰", title: "History", hint: "Browse, edit, export your posts", run: () => setRail("history") },
    { id: "calendar", icon: "📅", title: "Calendar", hint: "Scheduled & published posts by day", run: () => setRail("calendar") },
  ];

  const dock: { label: string; disabled: boolean; onClick: (() => void) | undefined } = (() => {
    if (generating) return { label: "Generating…", disabled: true, onClick: undefined };
    if (!selected) {
      if (!query.trim()) return { label: "Type a topic above", disabled: true, onClick: undefined };
      return { label: "✦ Generate post", disabled: false, onClick: () => handleGenerate() };
    }
    if (published && edits.dirty) return { label: "Save revision", disabled: busy, onClick: handleSave };
    if (published) return { label: "Republish revision", disabled: busy, onClick: () => publish(true) };
    if (edits.dirty) return { label: "Save edits", disabled: busy, onClick: handleSave };
    if (selected.approval_status === "APPROVED") {
      return { label: "Publish to LinkedIn", disabled: busy, onClick: () => publish() };
    }
    return { label: "✓ Approve & publish", disabled: busy, onClick: () => approve(true) };
  })();

  const activeRecordId = selected?.record_id ?? null;

  const goHome = () => {
    setRail("create");
    selectRecord(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const copyForLinkedIn = async () => {
    try {
      await navigator.clipboard.writeText(
        toLinkedInText(composeHashtagLine(edits.draft, edits.tags)),
      );
      notify("Copied — ready to paste into LinkedIn");
    } catch {
      notify("Clipboard unavailable", "error");
    }
  };

  const openGuidelines = () => {
    setGuidelinesOpen(true);
    if (guidelines) return;
    void api
      .guidelines()
      .then((d) => {
        setGuidelines(d.groups);
        setGuidelinesSource(d.source);
        setGuidelinesDisclaimer(d.disclaimer);
      })
      .catch(() => undefined);
  };

  return (
    <div className="min-h-screen">
      {/* ─── top bar ─────────────────────────────────────────── */}
      <header className="u-header sticky top-0 z-40 border-b" style={{ borderColor: "var(--line)" }}>
        <div className="mx-auto flex max-w-[96rem] items-center justify-between gap-3 px-3 py-1.5 sm:px-5 sm:py-2">
          <button
            type="button"
            onClick={goHome}
            aria-label="PostCraft — go to home"
            title="Back to Create"
            className="flex min-w-0 items-center gap-2.5 rounded-lg text-left transition hover:opacity-90"
          >
            <img src="/favicon.png" alt="" className="brand-logo h-7 w-7 shrink-0 rounded-md" />
            <span className="min-w-0" aria-hidden="true">
              <span
                className="block truncate text-sm font-bold leading-tight"
                style={{ color: "var(--ink)" }}
              >
                PostCraft
              </span>
              <span
                className="hidden font-mono text-[9px] uppercase leading-tight tracking-[0.12em] xl:block"
                style={{ color: "var(--faint)" }}
              >
                Generate · Review · Approve · Publish
              </span>
            </span>
          </button>
          <h1 className="sr-only">PostCraft</h1>
          {isDesktop ? (
            <ThemeToggle />
          ) : (
            <MobileMenu user={user} onSignOut={handleSignOut} onGuidelines={openGuidelines} />
          )}
        </div>
      </header>

      <main className="mx-auto max-w-[96rem] px-3 pb-28 pt-5 sm:px-5 sm:pb-32 sm:pt-6 lg:h-[calc(100vh-3.375rem)] lg:overflow-hidden lg:py-6">
        <div className="grid gap-6 lg:h-full lg:grid-cols-[256px_1fr] lg:items-stretch">
          {/* ─── sidebar: workspace nav + account ────────────── */}
          <nav
            className="side-nav hidden lg:flex lg:h-full lg:flex-col lg:pt-5"
            aria-label="Workspace"
          >
            <div className="side-group hidden shrink-0 lg:block">
              <p className="side-eyebrow">Workspace</p>
              <ul className="space-y-0.5">
                {(
                  [
                    { id: "create", icon: "＋", label: "Create", hint: "Draft a new post" },
                    { id: "history", icon: "☰", label: "History", hint: "Browse & export" },
                    { id: "calendar", icon: "📅", label: "Calendar", hint: "Posts by day" },
                  ] as Array<{ id: RailMode; icon: string; label: string; hint: string }>
                ).map((t) => {
                  const active = rail === t.id && !selected;
                  return (
                    <li key={t.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setRail(t.id);
                          selectRecord(null);
                        }}
                        aria-current={active ? "page" : undefined}
                        className="side-item"
                      >
                        <span className="side-item__icon" aria-hidden="true">
                          {t.icon}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="side-item__label">{t.label}</span>
                          <span className="side-item__hint">{t.hint}</span>
                        </span>
                        {t.id === "history" && historyTotal > 0 && <span className="side-count">{historyTotal}</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className="side-group hidden shrink-0 lg:block">
              <p className="side-eyebrow">Compliance</p>
              <button type="button" onClick={openGuidelines} className="side-item">
                <span className="side-item__icon" aria-hidden="true">
                  ✓
                </span>
                <span className="min-w-0 flex-1">
                  <span className="side-item__label">LinkedIn guidelines</span>
                  <span className="side-item__hint">We follow LinkedIn's rules</span>
                </span>
              </button>
            </div>

            {selected ? (
              <div className="side-group hidden shrink-0 lg:block">
                <p className="side-eyebrow">Review &amp; edit</p>
                <ul className="space-y-0.5">
                  {REVIEW_SECTIONS.map((s) => {
                    const active = reviewSectionId === s.id;
                    return (
                      <li key={s.id}>
                        <button
                          type="button"
                          onClick={() => goToReviewSection(s.id)}
                          aria-current={active ? "location" : undefined}
                          className="side-item"
                        >
                          <span className="side-item__icon" aria-hidden="true">
                            {s.step}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="side-item__label">{s.label}</span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : null}

            {/* ─── account: flush into the bottom corners ──────── */}
            <div className="side-foot shrink-0">
              <p className="side-eyebrow">Account</p>
              <div className="side-account">
                {user.picture_url ? (
                  <img src={user.picture_url} alt="" className="h-8 w-8 shrink-0 rounded-full" />
                ) : (
                  <div
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
                    style={{ background: "linear-gradient(135deg,#2f6fed,#7b2ff7)" }}
                    aria-hidden="true"
                  >
                    {user.name
                      .split(" ")
                      .map((w) => w[0])
                      .join("")
                      .slice(0, 2)
                      .toUpperCase()}
                  </div>
                )}
                <span className="side-account__name">{user.name}</span>
                <button
                  type="button"
                  onClick={handleSignOut}
                  title="Sign out"
                  aria-label="Sign out"
                  className="side-account__out"
                >
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
                    <path d="M10 3H5.5A2.5 2.5 0 0 0 3 5.5v13A2.5 2.5 0 0 0 5.5 21H10v-2H5.5a.5.5 0 0 1-.5-.5v-13a.5.5 0 0 1 .5-.5H10V3zm5.6 4.4L14.2 8.8l2.2 2.2H8v2h8.4l-2.2 2.2 1.4 1.4L20 12l-4.4-4.6z" />
                  </svg>
                </button>
              </div>
            </div>
          </nav>

          {/* ─── workspace: categorized review flow ─────────── */}
          <div className="side-scroll relative order-1 min-w-0 space-y-5 overflow-visible lg:order-none lg:h-full lg:overflow-y-auto">
            {generating && <GeneratingOverlay />}
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

            {!selected ? (
              <>
              {rail === "create" ? (
                <PostGenerator
                  query={query}
                  setQuery={setQuery}
                  language={language}
                  setLanguage={setLanguage}
                  formatting={formatting}
                  setFormatting={setFormatting}
                  includeImage={includeImage}
                  setIncludeImage={setIncludeImage}
                  generating={generating}
                  error={generating ? null : error}
                  onGenerate={handleGenerate}
                  voices={voices}
                  voiceId={voiceId}
                  setVoiceId={setVoiceId}
                  variations={variations}
                  setVariations={setVariations}
                  onToast={notify}
                />
              ) : rail === "calendar" ? (
                <CalendarView
                  selectedId={activeRecordId}
                  onSelect={async (id) => {
                    setBusy(true);
                    try {
                      selectRecord(await api.get(id));
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Failed to load post");
                    } finally {
                      setBusy(false);
                    }
                  }}
                  onToast={notify}
                />
              ) : (
                <div className="card card--flat rv flex h-full flex-col gap-3 p-4">
                  <SubTabs
                    ariaLabel="History sections"
                    value={histSub}
                    onChange={setHistSub}
                    tabs={[
                      { id: "posts", label: "Posts", icon: "☰", count: historyTotal },
                      { id: "filters", label: "Filters", icon: "⚙" },
                      { id: "stats", label: "Stats", icon: "▤" },
                    ]}
                  />
                  {histSub === "posts" ? (
                    <PostHistory
                      filters={filters}
                      reloadKey={historyTick}
                      selectedId={activeRecordId}
                      onTotal={setHistoryTotal}
                      onCounts={setHistCounts}
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
                      onDuplicate={(rec) => selectRecord(rec)}
                      onToast={notify}
                    />
                  ) : histSub === "filters" ? (
                    <FilterBar
                      filters={filters}
                      onChange={(f) => {
                        setFilters(f);
                      }}
                    />
                  ) : (
                    <div className="grid grid-cols-2 gap-2.5 text-center sm:grid-cols-5">
                      {(
                        [
                          ["All", histCounts?.total ?? 0],
                          ["Review", histCounts?.ready_for_review ?? 0],
                          ["Scheduled", histCounts?.scheduled ?? 0],
                          ["Published", histCounts?.published ?? 0],
                          ["Failed", histCounts?.failed ?? 0],
                        ] as Array<[string, number]>
                      ).map(([label, n]) => (
                        <div key={label} className="rounded-xl border px-2 py-2.5" style={{ borderColor: "var(--line)", background: "var(--surface)" }}>
                          <div className="text-xl font-bold" style={{ color: "var(--ink)" }}>
                            {n}
                          </div>
                          <div className="label !text-[10px]">{label}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
              </>
            ) : null}

            {!selected ? null : (
              <>
                <div className="sticky top-[57px] z-30 -mx-3 flex items-center gap-2 bg-[var(--header-bg)] px-3 py-1.5 backdrop-blur sm:-mx-5 sm:top-[61px] sm:px-5 lg:hidden">
                  <SectionNav items={REVIEW_SECTIONS} />
                  <button
                    type="button"
                    onClick={() => selectRecord(null)}
                    className="btn-ghost !px-2.5 !py-1.5 text-xs"
                  >
                    ← Back to {rail === "create" ? "Create" : rail === "history" ? "History" : "Calendar"}
                  </button>
                </div>
                {/* post header */}
                <div className="card rv flex flex-wrap items-center gap-2 p-4">
                  <span
                    className="rounded-full border px-2.5 py-1 font-mono text-[11px]"
                    style={{ borderColor: "var(--line-2)", color: "var(--muted)" }}
                    title={`${selected.record_id} · ${formatLocalTime(selected.created_at)}`}
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
                <section id="sec-review" className="section-card rv scroll-mt-28 lg:scroll-mt-20 section-emphasis">
                  <header className="section-head">
                    <span className="section-step">1</span>
                    <div>
                      <h2 className="text-base font-bold" style={{ color: "var(--ink)" }}>
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
                        <div className="mb-1.5 flex items-center justify-between gap-2">
                          <p className="label !mb-0">Post editor</p>
                          <button
                            type="button"
                            onClick={() => void copyForLinkedIn()}
                            className="btn-ghost !px-2.5 !py-1 text-xs"
                            title="Copy without markdown, ready to paste into LinkedIn"
                          >
                            Copy for LinkedIn
                          </button>
                        </div>
                        <PostEditor
                          text={edits.draft}
                          onChange={(d) => setEdits((e) => ({ ...e, draft: d, dirty: true }))}
                        />
                        <p className="hint mt-1.5" style={{ color: "var(--faint)" }}>
                          <strong>Bold</strong> here becomes real bold on LinkedIn — “Copy for LinkedIn”
                          converts it to Unicode bold, and publishing does the same automatically.
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
                          bumpHistory();
                        }}
                      />
                    </div>
                  </div>
                </section>

                {/* 02 · Visual */}
                <section id="sec-visual" className="section-card rv scroll-mt-28 lg:scroll-mt-20">
                  <header className="section-head">
                    <span className="section-step">2</span>
                    <div>
                      <h2 className="text-sm font-bold" style={{ color: "var(--ink)" }}>
                        Visual
                      </h2>
                      <p className="hint">
                        {selected.image_url
                          ? "On-topic image in the selected language — regenerate anytime."
                          : "Text-only post — add an image if you want one."}
                      </p>
                    </div>
                  </header>
                  <ImagePreview
                    url={selected.image_url ?? ""}
                    prompt={selected.image_prompt}
                    busy={busy}
                    analysis={selected.image_analysis}
                    onRegenerate={regenImage}
                    onUpload={uploadImage}
                  />
                </section>

                {/* 03 · Quality gate */}
                <section id="sec-quality" className="section-card rv scroll-mt-28 lg:scroll-mt-20">
                  <details className="group list-none" aria-label="Quality gate details">
                    <summary className="flex cursor-pointer select-none items-center justify-between gap-3 [&::-webkit-details-marker]:hidden">
                      <header className="section-head !mb-0">
                        <span className="section-step">3</span>
                        <div>
                          <h2 className="text-sm font-bold" style={{ color: "var(--ink)" }}>
                            Quality gate
                          </h2>
                          <p className="hint">Automatic validation before anything goes live.</p>
                        </div>
                      </header>
                      <span className="flex shrink-0 items-center gap-1.5">
                        <span
                          className="rounded-full px-2.5 py-1 text-[11px] font-bold"
                          style={{
                            background: selected.validation_result?.valid ? "var(--ok-soft)" : "var(--bad-soft)",
                            color: selected.validation_result?.valid ? "var(--ok)" : "var(--bad)",
                          }}
                        >
                          {selected.validation_result?.valid ? "PASSED" : "FAILED"}
                        </span>
                        <span
                          className="rounded-full px-2.5 py-1 text-[11px] font-bold"
                          style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
                        >
                          {Math.round((selected.validation_result?.quality_score ?? 0) * 100)}%
                        </span>
                        <span
                          className="chev text-xs transition-transform duration-200 group-open:rotate-180"
                          style={{ color: "var(--faint)" }}
                        >
                          ▾
                        </span>
                      </span>
                    </summary>
                    <div className="mt-3 space-y-2 rounded-xl p-4 text-sm" style={{ background: "var(--surface-2)" }}>
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
                      {!(selected.validation_result?.issues?.length) && !(selected.validation_result?.suggestions?.length) && (
                        <p className="text-xs" style={{ color: "var(--faint)" }}>
                          No issues or suggestions — this draft is ready to publish.
                        </p>
                      )}
                      <div className="flex items-center justify-between text-xs">
                        <span style={{ color: "var(--faint)" }}>Audience</span>
                        <span className="truncate pl-3" style={{ color: "var(--muted)" }}>
                          {selected.audience || "—"}
                        </span>
                      </div>
                    </div>
                  </details>
                </section>

                {/* 04 · Hashtags & publish */}
                <section id="sec-hashtags" className="section-card rv scroll-mt-28 lg:scroll-mt-20">
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
                      onApprove={(scheduledAt) => approve(true, scheduledAt)}
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
                            <span className="shrink-0" style={{ color: "var(--faint)" }} title={formatLocalTime(h.at)}>
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
        className="fixed inset-x-0 bottom-0 z-40 border-t px-3 py-2.5 lg:hidden"
        style={{ borderColor: "var(--line)", background: "var(--header-bg)", backdropFilter: "blur(8px)" }}
      >
        {!selected && (
          <div className="mx-auto mb-2 grid max-w-7xl grid-cols-3 gap-1.5">
            {(
              [
                { id: "create", label: "Create" },
                { id: "history", label: "History" },
                { id: "calendar", label: "Calendar" },
              ] as Array<{ id: RailMode; label: string }>
            ).map((t) => {
              const tabsActive = rail === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tabsActive}
                  onClick={() => setRail(t.id)}
                  className="flex items-center justify-center gap-1.5 rounded-xl px-2 py-2 text-[11px] font-semibold transition-all"
                  style={{
                    background: tabsActive ? "linear-gradient(135deg,var(--accent),var(--accent-2))" : "transparent",
                    color: tabsActive ? "var(--btn-ink)" : "var(--faint)",
                    boxShadow: tabsActive
                      ? "0 2px 10px color-mix(in srgb, var(--accent) 35%, transparent)"
                      : "none",
                  }}
                >
                  <span>{t.id === "create" ? "＋" : t.id === "history" ? "☰" : t.id === "calendar" ? "📅" : "📈"}</span>
                  {t.label}
                </button>
              );
            })}
          </div>
        )}
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

      {/* ─── variant picker ─────────────────────────────────── */}
      {variants && variants.length > 0 && (
        <VariationPicker
          items={variants}
          onPick={(rec) => {
            selectRecord(rec);
            bumpHistory();
            setVariants(null);
            notify("Favourite chosen — delete the others anytime from History", "success");
          }}
          onClose={() => setVariants(null)}
        />
      )}

      {/* ─── command palette ────────────────────────────────── */}
      <CommandMenu
        open={cmdOpen}
        onClose={() => setCmdOpen(false)}
        commands={paletteCommands}
        onSubmitText={(text) => {
          setRail("create");
          handleGenerate(text);
        }}
      />

      {guidelinesOpen && (
        <GuidelinesPanel
          groups={guidelines}
          source={guidelinesSource}
          disclaimer={guidelinesDisclaimer}
          loading={!guidelines}
          onClose={() => setGuidelinesOpen(false)}
        />
      )}

      {/* ─── toasts ────────────────────────────────────────── */}
      <div className="pointer-events-none fixed right-3 top-[52px] z-[60] flex w-[calc(100%-1.5rem)] max-w-sm flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="toast-in pointer-events-auto flex flex-col overflow-hidden rounded-xl border shadow-lg"
            style={{
              borderColor: t.kind === "success" ? "var(--ok-soft)" : "var(--bad-soft)",
              background: t.kind === "success" ? "var(--ok-soft)" : "var(--bad-soft)",
              color: t.kind === "success" ? "var(--ok)" : "var(--bad)",
            }}
          >
            <div className="flex items-start gap-2 px-4 py-2.5 text-sm font-medium">
              <span className="shrink-0 font-bold">{t.kind === "success" ? "✓" : "✕"}</span>
              <span className="min-w-0 flex-1">{t.text}</span>
              {t.action && (
                <button
                  type="button"
                  onClick={() => {
                    t.action?.onClick();
                    setToasts((x) => x.filter((y) => y.id !== t.id));
                  }}
                  className="shrink-0 rounded-lg border px-2 py-0.5 text-xs font-bold transition hover:opacity-80"
                  style={{ borderColor: "currentColor" }}
                >
                  {t.action.label}
                </button>
              )}
            </div>
            <div className="h-0.5" style={{ background: "color-mix(in srgb, currentColor 25%, transparent)" }}>
              <div className="toast-bar h-full" style={{ background: "currentColor" }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}