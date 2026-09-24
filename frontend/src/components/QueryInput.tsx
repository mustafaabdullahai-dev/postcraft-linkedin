import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import type { SuggestResponse } from "../types";

interface Props {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  onSubmit?: () => void;
  autoFocus?: boolean;
}

const MIN_CHARS = 12;
const DEBOUNCE_MS = 700;

export default function QueryInput({ value, onChange, placeholder, onSubmit, autoFocus }: Props) {
  const [suggestion, setSuggestion] = useState<SuggestResponse | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ctrl = useRef<AbortController | null>(null);
  const lastSought = useRef("");

  const clear = useCallback(() => {
    if (ctrl.current) ctrl.current.abort();
    if (timer.current) clearTimeout(timer.current);
    setSuggestion(null);
    setSuggesting(false);
  }, []);

  useEffect(() => clear, [clear]);

  const seek = useCallback(
    (raw: string) => {
      const text = raw.trim();
      if (text.length < MIN_CHARS || text === lastSought.current) return;
      lastSought.current = text;
      ctrl.current?.abort();
      const ac = new AbortController();
      ctrl.current = ac;
      setSuggesting(true);
      setSuggestion(null);
      api
        .suggest(text, ac.signal)
        .then((res) => {
          if (!ac.signal.aborted) {
            const improved = (res.improved ?? "").trim();
            setSuggestion(improved && !text.toLowerCase().includes(improved.toLowerCase()) ? res : null);
          }
        })
        .catch(() => {
          /* aborted or offline — silence */
        })
        .finally(() => {
          if (!ac.signal.aborted) setSuggesting(false);
        });
    },
    [],
  );

  const onType = (text: string) => {
    onChange(text);
    if (text.trim().length < MIN_CHARS) return clear();
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => seek(text), DEBOUNCE_MS);
  };

  const accept = () => {
    if (!suggestion) return;
    onChange(suggestion.improved);
    lastSought.current = suggestion.improved;
    clear();
    textareaRef.current?.focus();
  };

  return (
    <div className="space-y-3">
      <div>
        <p className="label mb-1.5">Topic</p>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onType(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Tab" && suggestion && !e.shiftKey) {
              e.preventDefault();
              accept();
              return;
            }
            if (e.key === "Enter" && !e.shiftKey && onSubmit) {
              e.preventDefault();
              onSubmit();
            }
          }}
          placeholder={placeholder ?? "Write your topic — e.g. Why agentic AI is reshaping software teams"}
          rows={3}
          autoFocus={autoFocus}
          className="input resize-none leading-relaxed"
        />
        <p className="hint mt-1.5">
          <kbd className="kbd">Enter</kbd> to generate · <kbd className="kbd">Shift+Enter</kbd> new line ·{" "}
          <kbd className="kbd">Tab</kbd> accepts the suggestion
        </p>
      </div>

      {suggesting && (
        <div className="flex items-center gap-2 text-xs text-[var(--muted)]">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--line-2)] border-t-[var(--accent)]" />
          Sharpening your question…
        </div>
      )}

      {suggestion && (
        <button type="button" onClick={accept} className="suggestion w-full" title="Click or press Tab to use">
          <span className="tag tag--mint shrink-0">Better</span>
          <span className="min-w-0 flex-1 text-left">
            <span className="block text-sm font-medium leading-snug text-[var(--ink)]">
              {suggestion.improved}
            </span>
            <span className="mt-0.5 block text-[11px] text-[var(--faint)]">{suggestion.note}</span>
          </span>
          <span className="kbd shrink-0 self-center">Tab</span>
        </button>
      )}
    </div>
  );
}