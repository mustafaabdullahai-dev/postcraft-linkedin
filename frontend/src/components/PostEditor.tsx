import { useEffect, useState } from "react";

interface Props {
  text: string;
  onChange: (text: string) => void;
  disabled?: boolean;
}

export default function PostEditor({ text, onChange, disabled }: Props) {
  const [draft, setDraft] = useState(text);

  useEffect(() => setDraft(text), [text]);

  const charCount = draft.length;
  const hasEmoji = /\p{Emoji}/u.test(draft);

  return (
    <div className="space-y-2">
      <textarea
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value);
          onChange(e.target.value);
        }}
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