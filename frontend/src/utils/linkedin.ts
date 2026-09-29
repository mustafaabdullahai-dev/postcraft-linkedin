/**
 * Convert markdown emphasis into the text LinkedIn actually renders.
 *
 * LinkedIn's feed has no markdown parser, but it *does* render the Unicode
 * Mathematical Alphanumeric Symbols — so `**bold**` is converted to real bold
 * characters and stays visually bold on the feed, instead of showing asterisks.
 * This mirrors the backend `app/services/linkedin.py::to_linkedin_text`, so a
 * copied post matches exactly what the API publishes. Written without lookbehind
 * assertions so it also parses on Safari < 16.4.
 */
const BOLD_RANGES: Array<[number, number, number]> = [
  [65, 90, 0x1d400], // A-Z
  [97, 122, 0x1d41a], // a-z
  [48, 57, 0x1d7ce], // 0-9
];

export function toUnicodeBold(text: string): string {
  let out = "";
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0;
    const range = BOLD_RANGES.find(([lo, hi]) => cp >= lo && cp <= hi);
    out += range ? String.fromCodePoint(range[2] + cp - range[0]) : ch;
  }
  return out;
}

/**
 * Replace any existing hashtag line with the authoritative tag list.
 * Mirrors the backend `clean_post` so the copied text matches what is published
 * — a user can edit the tag list without touching the draft text.
 */
export function composeHashtagLine(text: string, hashtags: string[]): string {
  const isTagLine = (line: string) => {
    const tokens = line.trim().split(/\s+/).filter(Boolean);
    return tokens.length > 0 && tokens.every((t) => t.startsWith("#"));
  };
  const isLabel = (line: string) => /^#?\s*hashtags:?\s*$/i.test(line.trim());
  const kept = text.split("\n").filter((l) => !isLabel(l) && !isTagLine(l));
  const body = kept.join("\n").trim();
  const tags = hashtags.filter((h) => h.startsWith("#")).join(" ");
  return tags ? `${body}\n\n${tags}` : body;
}

export function toLinkedInText(text: string): string {
  if (!text) return "";
  const blocks: string[] = [];
  const stash = (value: string) => `\u0000${blocks.push(value) - 1}\u0000`;

  // Code keeps its contents verbatim (so `**kwargs` survives).
  let out = text
    .replace(/```[\s\S]*?```/g, (m) => stash(m.slice(3, -3).replace(/^\n+|\n+$/g, "")))
    .replace(/`([^`\n]+)`/g, (_m, code: string) => stash(code));

  out = out
    .replace(/^[ \t]{0,3}#{1,6}[ \t]+/gm, "")
    .replace(/^[ \t]{0,3}>[ \t]?/gm, "")
    .replace(/^[ \t]*[*+\-][ \t]+/gm, "• ")
    .replace(/~~([^~\n]+)~~/g, "$1")
    // Emphasis needs non-space edges (so "2 * 3" and "a * b" survive), matching
    // the backend's `_EMPHASIS` behaviour.
    .replace(/\*\*\*(?!\s)([^*\n]*[^\s*])\*\*\*/g, (_m, inner: string) => toUnicodeBold(inner))
    .replace(/\*\*(?!\s)([^*\n]*[^\s*])\*\*/g, (_m, inner: string) => toUnicodeBold(inner))
    .replace(/__(?!\s)([^_\n]*[^\s_])__(?![\w_])/g, (_m, inner: string) => toUnicodeBold(inner))
    .replace(/(^|[^\w*])\*(?!\s)([^*\n]*[^\s*])\*(?=[^\w*]|$)/g, "$1$2")
    .replace(/(^|[^\w_])_(?!\s)([^_\n]*[^\s_])_(?=[^\w_]|$)/g, "$1$2")
    // Leftover marker runs are only removed when they are NOT space-separated
    // (so "a ** b ** c" keeps its asterisks), matching the backend.
    .replace(/(^|\S)\*{2,3}(?=\S)/g, "$1")
    .replace(/(^|\S)_{2,3}(?=\S)/g, "$1")
    .replace(/\n{3,}/g, "\n\n");

  return out.replace(/\u0000(\d+)\u0000/g, (_m, i: string) => blocks[Number(i)] ?? "");
}
