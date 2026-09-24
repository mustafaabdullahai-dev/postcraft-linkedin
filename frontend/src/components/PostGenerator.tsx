import { useEffect, useRef, useState } from "react";
import type { FormattingPrefs } from "../types";
import ErrorAlert from "./ErrorAlert";
import FormattingControls from "./FormattingControls";
import GenerationProgress from "./GenerationProgress";
import LanguageSelect from "./LanguageSelect";
import QueryInput from "./QueryInput";

interface Props {
  query: string;
  setQuery: (q: string) => void;
  language: string;
  setLanguage: (l: string) => void;
  formatting: FormattingPrefs;
  setFormatting: (f: FormattingPrefs) => void;
  generating: boolean;
  error: string | null;
  onGenerate: (topic?: string) => void;
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
  generating,
  error,
  onGenerate,
}: Props) {
  const [elapsed, setElapsed] = useState(0);
  const [showAdvanced, setShowAdvanced] = useState(false);
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

  return (
    <div className="card rv space-y-4 p-5">
      <div className="space-y-1">
        <p className="label">Create</p>
        <h2 className="text-lg font-bold text-[var(--ink)]">Say it once, AI sharpens it.</h2>
        <p className="hint">
          Type a raw topic — the assistant rewrites it live. Then it drafts, validates quality, and generates an image
          you review before publishing.
        </p>
      </div>
      <QueryInput
        value={query}
        onChange={setQuery}
        onSubmit={generating ? undefined : onGenerate}
        placeholder="e.g. Why agentic AI is reshaping software teams"
        autoFocus
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
        <button
          type="button"
          onClick={() => setShowAdvanced((s) => !s)}
          aria-expanded={showAdvanced}
          className="flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-xs font-semibold transition"
          style={{ borderColor: "var(--line-2)", color: showAdvanced ? "var(--accent)" : "var(--muted)" }}
        >
          <span>Style &amp; size — for expert touches</span>
          <svg
            viewBox="0 0 24 24"
            className="h-4 w-4 fill-current transition-transform"
            style={{ transform: showAdvanced ? "rotate(180deg)" : "rotate(0deg)" }}
            aria-hidden="true"
          >
            <path d="M12 15.5 4.5 8l1.4-1.4L12 12.7l6.1-6.1L19.5 8z" />
          </svg>
        </button>
        {showAdvanced && (
          <div className="toast-in mt-3">
            <FormattingControls value={formatting} onChange={setFormatting} />
          </div>
        )}
      </div>
      {generating ? (
        <GenerationProgress elapsed={elapsed} />
      ) : (
        <button type="button" onClick={() => onGenerate()} disabled={!query.trim()} className="btn-primary w-full py-3">
          ✦ Generate post
        </button>
      )}
      <ErrorAlert message={error} />
    </div>
  );
}