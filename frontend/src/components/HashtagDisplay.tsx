import { useState } from "react";

interface Props {
  /** Tags currently included in the post. */
  hashtags: string[];
  /** Full LLM-generated candidate pool (selected + droppable). */
  candidates?: string[];
  editing?: boolean;
  onChange?: (tags: string[]) => void;
}

export default function HashtagDisplay({ hashtags, candidates, editing, onChange }: Props) {
  const [input, setInput] = useState("");

  const pool = Array.from(
    new Set([...(candidates ?? []), ...hashtags].map((t) => (t.startsWith("#") ? t.toLowerCase() : `#${t.toLowerCase()}`))),
  );

  const toggle = (tag: string) => {
    if (!onChange) return;
    onChange(hashtags.includes(tag) ? hashtags.filter((t) => t !== tag) : [...hashtags, tag]);
  };

  const commitInput = () => {
    if (!onChange || !input.trim()) return;
    const next = input
      .split(/[\s,#]+/)
      .filter(Boolean)
      .map((t) => (t.startsWith("#") ? t.toLowerCase() : `#${t.toLowerCase()}`));
    if (!next.length) return;
    const tags = [...hashtags];
    for (const t of next) if (!tags.includes(t)) tags.push(t);
    onChange(tags);
    setInput("");
  };

  return (
    <div className="space-y-2.5">
      {pool.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {pool.map((tag) => {
            const selected = hashtags.includes(tag);
            return (
              <button
                key={tag}
                type="button"
                onClick={() => toggle(tag)}
                disabled={!editing || !onChange}
                className={selected ? "chip-selected" : "chip-unselected"}
                title={selected ? "click to drop this tag" : "click to include this tag"}
              >
                <svg
                  viewBox="0 0 16 16"
                  className="h-3.5 w-3.5"
                  fill={selected ? "currentColor" : "none"}
                  stroke="currentColor"
                  strokeWidth={selected ? 0 : 1.6}
                  aria-hidden="true"
                >
                  {selected ? (
                    <path d="M13.9 3.6a.9.9 0 0 0-1.3-.1L6.6 9.4 4.2 7.1a.9.9 0 0 0-1.4 1.2l3 3a.9.9 0 0 0 1.4-.1l6.7-6.6a.9.9 0 0 0 0-1z" />
                  ) : (
                    <rect x="1.5" y="1.5" width="13" height="13" rx="3" />
                  )}
                </svg>
                {tag}
              </button>
            );
          })}
        </div>
      )}

      {editing && onChange && (
        <div className="flex items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === ",") {
                e.preventDefault();
                commitInput();
              }
            }}
            onBlur={commitInput}
            placeholder="add a tag…"
            className="input !w-44 !rounded-full !py-1.5 !text-xs"
          />
          <p className="hint">
            Toggle generated tags · LLM-picked for SEO, you curate the final set.
          </p>
        </div>
      )}
    </div>
  );
}