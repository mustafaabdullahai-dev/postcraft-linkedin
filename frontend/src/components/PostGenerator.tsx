import { useEffect, useRef, useState } from "react";
import type { FormattingPrefs, VoiceProfile } from "../types";
import ErrorAlert from "./ErrorAlert";
import FormattingControls from "./FormattingControls";
import GenerationProgress from "./GenerationProgress";
import LanguageSelect from "./LanguageSelect";
import QueryInput from "./QueryInput";
import SubTabs from "./SubTabs";
import VoicePicker from "./VoicePicker";

interface Props {
  query: string;
  setQuery: (q: string) => void;
  language: string;
  setLanguage: (l: string) => void;
  formatting: FormattingPrefs;
  setFormatting: (f: FormattingPrefs) => void;
  includeImage: boolean;
  setIncludeImage: (v: boolean) => void;
  generating: boolean;
  error: string | null;
  onGenerate: (topic?: string) => void;
  voices: VoiceProfile[];
  voiceId: string;
  setVoiceId: (id: string) => void;
  variations: number;
  setVariations: (n: number) => void;
  onToast: (text: string, kind?: "success" | "error") => void;
}

const SUGGESTED_TOPICS = [
  "Why remote work is here to stay",
  "Lessons from migrating to microservices",
  "A hiring loop candidates actually love",
  "The hidden cost of context switching",
];

export default function PostGenerator({
  query,
  setQuery,
  language,
  setLanguage,
  formatting,
  setFormatting,
  includeImage,
  setIncludeImage,
  generating,
  error,
  onGenerate,
  voices,
  voiceId,
  setVoiceId,
  variations,
  setVariations,
  onToast,
}: Props) {
  const [elapsed, setElapsed] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (generating) {
      setElapsed(0);
      timer.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    } else if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [generating]);

  const [sub, setSub] = useState<"topic" | "voice" | "style">("topic");

  return (
    <div className="card card--flat rv flex min-h-full flex-col gap-3 p-5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1 space-y-1">
          <p className="label">Create</p>
          <h2 className="text-lg font-bold text-[var(--ink)]">Say it once, AI sharpens it.</h2>
          <p className="hint">
            Type a raw topic — the assistant rewrites it live. Then it drafts, validates quality, and generates an image
            you review before publishing.
          </p>
        </div>
        {!generating && (
          <div className="hidden shrink-0 lg:block">
            <button
              type="button"
              onClick={() => onGenerate()}
              disabled={!query.trim()}
              className="btn-primary !bg-[#0A66C2] px-6 !text-white transition hover:!bg-[#0855a6]"
            >
              ✦ Generate post
            </button>
          </div>
        )}
      </div>
      <SubTabs
        ariaLabel="Create sections"
        value={sub}
        onChange={setSub}
        tabs={[
          { id: "topic", label: "Topic", icon: "✎" },
          { id: "voice", label: "Voice", icon: "◍" },
          { id: "style", label: "Style", icon: "≡" },
        ]}
      />

      {sub === "topic" ? (
        <>
          <QueryInput
            value={query}
            onChange={setQuery}
            onSubmit={generating ? undefined : onGenerate}
            placeholder="e.g. Why agentic AI is reshaping software teams"
          />
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="hint mr-1">Try:</span>
            {SUGGESTED_TOPICS.map((t) => (
              <button
                key={t}
                type="button"
                disabled={generating}
                onClick={() => onGenerate(t)}
                className="chip-unselected !px-2 !py-1 disabled:opacity-50"
              >
                {t}
              </button>
            ))}
          </div>
          <LanguageSelect value={language} onChange={setLanguage} />

          <div>
            <span className="label !mb-1">Output</span>
            <div className="grid grid-cols-2 gap-2">
              {(
                [
                  { v: true, icon: "🖼", label: "Text + image", hint: "Post with a visual" },
                  { v: false, icon: "✎", label: "Text only", hint: "Faster, no image" },
                ] as Array<{ v: boolean; icon: string; label: string; hint: string }>
              ).map((o) => {
                const active = includeImage === o.v;
                return (
                  <button
                    key={String(o.v)}
                    type="button"
                    onClick={() => setIncludeImage(o.v)}
                    disabled={generating}
                    aria-pressed={active}
                    className="flex flex-col items-start gap-0.5 rounded-xl border px-3 py-2 text-left transition disabled:opacity-50"
                    style={{
                      borderColor: active ? "var(--accent)" : "var(--line)",
                      background: active ? "var(--accent-soft)" : "var(--surface)",
                      color: active ? "var(--accent-ink)" : "var(--ink-soft)",
                    }}
                  >
                    <span className="text-xs font-semibold">
                      <span aria-hidden="true">{o.icon}</span> {o.label}
                    </span>
                    <span className="text-[10px] opacity-80">{o.hint}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </>
      ) : sub === "voice" ? (
      <div className="space-y-3">
        <div>
          <div className="mb-1 flex items-center justify-between">
            <label className="label !mb-0">Your voice</label>
            <div className="flex items-center gap-1.5">
              <label htmlFor="variations" className="hint !mb-0">
                Drafts:
              </label>
              <select
                id="variations"
                value={variations}
                onChange={(e) => setVariations(Number(e.target.value))}
                disabled={generating}
                className="select !h-7 w-auto !py-0 !text-[11px]"
                aria-label="Number of drafts to generate"
              >
                {[1, 2, 3].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <VoicePicker voices={voices} value={voiceId} onChange={setVoiceId} onToast={onToast} />
          {variations > 1 && (
            <p className="mt-1 text-[10px]" style={{ color: "var(--accent)" }}>
              ✨ {variations} drafts — pick your favourite after generating.
            </p>
          )}
        </div>
      </div>
      ) : (
        <div className="toast-in">
          <FormattingControls value={formatting} onChange={setFormatting} />
        </div>
      )}
      <ErrorAlert message={error} />
      {generating ? (
        <GenerationProgress elapsed={elapsed} />
      ) : (
        <div className="mt-auto lg:hidden">
          <button
            type="button"
            onClick={() => onGenerate()}
            disabled={!query.trim()}
            className="btn-primary w-full !bg-[#0A66C2] py-3.5 text-[15px] !text-white transition hover:!bg-[#0855a6]"
          >
            ✦ Generate post
          </button>
        </div>
      )}
    </div>
  );
}