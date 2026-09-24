import { useState } from "react";
import type { FormattingPrefs } from "../types";
import { FORMATTING_OPTIONS, POST_LENGTH_OPTIONS } from "../types";

interface Props {
  value: FormattingPrefs;
  onChange: (value: FormattingPrefs) => void;
}

const CUSTOM = -1;

function toggle(value: FormattingPrefs, key: keyof FormattingPrefs) {
  return { ...value, [key]: !value[key] };
}

export default function FormattingControls({ value, onChange }: Props) {
  const [customOpen, setCustomOpen] = useState(value.word_target > 0 && !POST_LENGTH_OPTIONS.some(
    (o) => o.value === value.word_target,
  ));
  const selectValue = customOpen ? CUSTOM : value.word_target;

  const setWords = (words: number) => {
    const word_target = Math.max(0, Math.min(1500, Math.round(words) || 0));
    onChange({ ...value, word_target });
  };

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <p className="label" title="Hook + body + CTA in words (hashtags excluded); the LLM aims close to this.">
          Post length (words)
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectValue}
            onChange={(e) => {
              const v = Number(e.target.value);
              if (v === CUSTOM) {
                setCustomOpen(true);
                if (value.word_target === 0) setWords(180);
              } else {
                setCustomOpen(false);
                setWords(v);
              }
            }}
            className="select h-9 font-medium"
          >
            {POST_LENGTH_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          {customOpen && (
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={1}
                max={1500}
                value={value.word_target || ""}
                onChange={(e) => setWords(Number(e.target.value))}
                className="select h-9 w-24 text-center font-medium"
                aria-label="Custom word count"
              />
              <span className="text-xs text-[var(--faint)]">words</span>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <p className="label">Style &amp; formatting</p>
        <div className="grid gap-1.5 sm:grid-cols-2">
        {FORMATTING_OPTIONS.map(({ key, label, hint }) => {
          const active = value[key];
          return (
            <button
              key={key}
              type="button"
              title={hint}
              onClick={() => onChange(toggle(value, key))}
              className={`flex items-start gap-2.5 rounded-lg border px-3 py-2 text-left transition-colors ${
                active
                  ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                  : "border-[var(--line-2)] bg-[var(--surface)] hover:border-[var(--line-strong)]"
              }`}
            >
              <span
                className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                  active ? "border-[var(--accent)] bg-[var(--accent)]" : "border-[var(--line-strong)] bg-[var(--surface)]"
                }`}
                aria-hidden="true"
              >
                {active && (
                  <svg viewBox="0 0 24 24" className="h-3 w-3 fill-white">
                    <path d="M9 16.17L5.53 12.7 4.12 14.1 9 19l11-11-1.41-1.4z" />
                  </svg>
                )}
              </span>
              <span className="block text-sm font-semibold" style={{ color: active ? "var(--accent-ink)" : "var(--ink-soft)" }}>
                {label}
              </span>
            </button>
          );
        })}
        </div>
      </div>
    </div>
  );
}