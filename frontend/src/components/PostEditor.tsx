import { useEffect, useRef, useState } from "react";

interface Props {
  text: string;
  onChange: (text: string) => void;
  disabled?: boolean;
}

const pill =
  "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition hover:opacity-90 disabled:opacity-50";

export default function PostEditor({ text, onChange, disabled }: Props) {
  const [draft, setDraft] = useState(text);
  const [panel, setPanel] = useState<"link" | "text" | null>(null);
  const [linkLabel, setLinkLabel] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [extra, setExtra] = useState("");
  const [caret, setCaret] = useState<number | null>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => setDraft(text), [text]);

  const charCount = draft.length;
  const hasEmoji = /\p{Emoji}/u.test(draft);

  const setText = (next: string) => {
    setDraft(next);
    onChange(next);
  };

  /**
   * Insert a snippet on its own line. Uses the last caret the user placed in the
   * editor; if they never clicked into it, append to the end (so the snippet
   * never lands at position 0 unexpectedly).
   */
  const insert = (snippet: string) => {
    const ta = taRef.current;
    const pos = Math.min(caret ?? draft.length, draft.length);
    const before = draft.slice(0, pos);
    const after = draft.slice(pos);
    const lead = before.length > 0 && !before.endsWith("\n") ? "\n" : "";
    const insertion = `${lead}${snippet}\n`;
    const next = before + insertion + after;
    setText(next);
    requestAnimationFrame(() => {
      const nextPos = before.length + insertion.length;
      setCaret(nextPos);
      ta?.focus();
      ta?.setSelectionRange(nextPos, nextPos);
    });
  };

  const urlValid = /^https?:\/\/\S+$/i.test(linkUrl.trim());

  // Where will a snippet land? Either the caret the user placed in the post, or
  // the end. Showing it removes the guesswork of "full editing at my position".
  const hasCaret = caret !== null && caret < draft.length;
  const at = Math.min(caret ?? draft.length, draft.length);
  const insertTarget = hasCaret
    ? `after “…${draft.slice(Math.max(0, at - 30), at).replace(/\s+/g, " ").trim()}”`
    : "at the end of the post";

  const addLink = () => {
    if (!urlValid) return;
    const label = linkLabel.trim();
    insert(label ? `${label}: ${linkUrl.trim()}` : linkUrl.trim());
    setLinkLabel("");
    setLinkUrl("");
    setPanel(null);
  };

  const addText = () => {
    const value = extra.trim();
    if (!value) return;
    insert(value);
    setExtra("");
    setPanel(null);
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={() => setPanel((p) => (p === "link" ? null : "link"))}
          aria-expanded={panel === "link"}
          disabled={disabled}
          className={pill}
          style={{ borderColor: "var(--line-2)", color: "var(--muted)", background: "var(--surface)" }}
        >
          🔗 Add link
        </button>
        <button
          type="button"
          onClick={() => setPanel((p) => (p === "text" ? null : "text"))}
          aria-expanded={panel === "text"}
          disabled={disabled}
          className={pill}
          style={{ borderColor: "var(--line-2)", color: "var(--muted)", background: "var(--surface)" }}
        >
          ✎ Add text
        </button>
        <span className="hint !mb-0 ml-auto hidden sm:inline">
          optional — click in the post to choose where it lands
        </span>
      </div>

      {panel === "link" && (
        <div
          className="toast-in grid gap-2 rounded-xl border p-2.5 sm:grid-cols-[1fr_1fr_auto]"
          style={{ borderColor: "var(--line-2)", background: "var(--surface-2)" }}
        >
          <input
            value={linkLabel}
            onChange={(e) => setLinkLabel(e.target.value)}
            placeholder="Link text (optional)"
            aria-label="Link text"
            className="input !h-9 !text-xs"
          />
          <input
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") addLink();
            }}
            placeholder="https://example.com"
            aria-label="Link URL"
            inputMode="url"
            className="input !h-9 !text-xs"
          />
          <button
            type="button"
            onClick={addLink}
            disabled={!urlValid}
            className="btn-primary !min-h-9 !py-1.5 text-xs"
          >
            Insert link
          </button>
          <p className="text-[10px] sm:col-span-3" style={{ color: "var(--faint)" }}>
            Inserts {insertTarget}
          </p>
        </div>
      )}

      {panel === "text" && (
        <div
          className="toast-in space-y-2 rounded-xl border p-2.5"
          style={{ borderColor: "var(--line-2)", background: "var(--surface-2)" }}
        >
          <textarea
            value={extra}
            onChange={(e) => setExtra(e.target.value)}
            rows={2}
            placeholder="Type the text to add…"
            aria-label="Text to add"
            className="input resize-y !text-xs"
          />
          <p className="text-[10px]" style={{ color: "var(--faint)" }}>
            Inserts {insertTarget}
          </p>
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setExtra("");
                setPanel(null);
              }}
              className="btn-ghost !min-h-9 !px-2.5 !py-1 text-xs"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={addText}
              disabled={!extra.trim()}
              className="btn-primary !min-h-9 !py-1.5 text-xs"
            >
              Add text
            </button>
          </div>
        </div>
      )}

      <textarea
        ref={taRef}
        value={draft}
        onChange={(e) => setText(e.target.value)}
        onSelect={(e) => setCaret(e.currentTarget.selectionStart)}
        onClick={(e) => setCaret(e.currentTarget.selectionStart)}
        onKeyUp={(e) => setCaret(e.currentTarget.selectionStart)}
        disabled={disabled}
        rows={14}
        className="input resize-y font-sans leading-relaxed"
        spellCheck={false}
      />
      <div className="flex items-center justify-between text-xs text-[var(--faint)]">
        <div className="space-x-4">
          <span className={charCount > 3000 ? "font-semibold text-[var(--bad)]" : ""}>{charCount} chars</span>
          <span>~{Math.round(charCount / 5)} words</span>
          {hasEmoji ? (
            <span className="font-medium text-[var(--ok)]">emoji detected</span>
          ) : (
            <span>no emoji yet</span>
          )}
        </div>
        <span className="hidden sm:inline">character count updates live</span>
      </div>
    </div>
  );
}
