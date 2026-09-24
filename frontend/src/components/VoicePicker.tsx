import { useEffect, useState } from "react";
import type { VoiceProfile } from "../types";
import { api } from "../services/api";

interface Props {
  voices: VoiceProfile[];
  value: string;
  onChange: (id: string) => void;
  onToast: (text: string, kind?: "success" | "error") => void;
}

export default function VoicePicker({ voices, value, onChange, onToast }: Props) {
  const [manage, setManage] = useState(false);
  const [draft, setDraft] = useState({ name: "", tone: "", audience: "", word_target: 0 });
  const [saving, setSaving] = useState(false);

  const selected = voices.find((v) => v.voice_id === value);

  const create = async () => {
    if (!draft.name.trim()) return;
    setSaving(true);
    try {
      const rec = await api.voiceProfiles.create({
        name: draft.name.trim(),
        tone: draft.tone.trim(),
        audience: draft.audience.trim(),
        word_target: draft.word_target,
      });
      onChange(rec.voice_id);
      setDraft({ name: "", tone: "", audience: "", word_target: 0 });
      onToast("Voice saved");
    } catch (e) {
      onToast(e instanceof Error ? e.message : "Couldn't save voice", "error");
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    if (value && !voices.some((v) => v.voice_id === value)) onChange("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voices]);

  return (
    <div className="space-y-2">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="select"
        aria-label="Brand voice"
      >
        <option value="">✨ Default — AI picks the tone</option>
        {voices.map((v) => (
          <option key={v.voice_id} value={v.voice_id}>
            {v.name}
          </option>
        ))}
      </select>
      <p className="hint">
        {selected
          ? `${selected.description || selected.tone || "Custom voice"} · ${selected.word_target ? `~${selected.word_target} words` : "auto length"}`
          : "Pick a saved voice, or add your own — tone, audience and length apply to every draft."}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => setManage((s) => !s)} className="btn-ghost !px-2 !py-1 text-[11px]">
          {manage ? "Close voice manager" : "Manage voices"}
        </button>
        {voices.length > 0 && (
          <span className="text-[11px]" style={{ color: "var(--faint)" }}>
            {voices.length} saved
          </span>
        )}
      </div>

      {manage && (
        <div className="space-y-3">
          <div className="space-y-2 rounded-xl border p-3" style={{ borderColor: "var(--line-2)" }}>
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={draft.name}
                onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
                placeholder="Voice name (e.g. Data Storyteller)"
                className="input !h-9 flex-1 !text-xs"
              />
              <input
                value={draft.word_target || ""}
                onChange={(e) => setDraft((d) => ({ ...d, word_target: Number(e.target.value) || 0 }))}
                type="number"
                min={0}
                max={1500}
                placeholder="Length (0 = auto)"
                className="input !h-9 w-28 !text-xs"
                title="Target word count, 0 = automatic"
              />
            </div>
            <input
              value={draft.tone}
              onChange={(e) => setDraft((d) => ({ ...d, tone: e.target.value }))}
              placeholder="Tone — e.g. analytical yet vivid"
              className="input !h-9 !text-xs"
            />
            <input
              value={draft.audience}
              onChange={(e) => setDraft((d) => ({ ...d, audience: e.target.value }))}
              placeholder="Audience — e.g. data teams and analytics leaders"
              className="input !h-9 !text-xs"
            />
            <button type="button" onClick={() => void create()} disabled={saving || !draft.name.trim()} className="btn-secondary w-full py-2 text-xs">
              {saving ? "Saving…" : "＋ Add voice"}
            </button>
          </div>

          <ul className="space-y-1.5">
            {voices.map((v) => (
              <li key={v.voice_id} className="flex items-center justify-between gap-2 rounded-lg px-2.5 py-2" style={{ background: "var(--surface-2)" }}>
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold" style={{ color: "var(--ink)" }}>
                    {v.name}
                  </p>
                  <p className="truncate text-[10px]" style={{ color: "var(--faint)" }}>
                    {v.tone || v.audience || v.description || "Custom"}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    onClick={() => onChange(v.voice_id)}
                    className={`rounded-md px-2 py-1 text-[11px] font-semibold transition ${value === v.voice_id ? "bg-[var(--accent)] text-[var(--accent-ink)]" : "hover:bg-[var(--surface)]"}`}
                  >
                    Use
                  </button>
                  <button
                    type="button"
                    title="Delete voice"
                    onClick={() =>
                      void api.voiceProfiles
                        .remove(v.voice_id)
                        .then(() => {
                          if (value === v.voice_id) onChange("");
                          onToast("Voice deleted");
                        })
                        .catch((e) => onToast(e instanceof Error ? e.message : "Delete failed", "error"))
                    }
                    className="rounded-md px-2 py-1 text-[11px] transition hover:text-[var(--bad)]"
                    style={{ color: "var(--faint)" }}
                  >
                    ✕
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}