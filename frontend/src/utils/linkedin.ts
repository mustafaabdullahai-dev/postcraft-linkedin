/**
 * Convert markdown emphasis into the plain text LinkedIn actually renders.
 *
 * LinkedIn's feed has no markdown parser, so `**bold**` shows up as literal
 * asterisks. This mirrors the backend `app/services/linkedin.py::to_plain_text`
 * so a copied post matches exactly what the API publishes. Written without
 * lookbehind assertions so it also parses on Safari < 16.4.
 */
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
    .replace(/\*\*\*([^*\n]+)\*\*\*/g, "$1")
    .replace(/\*\*([^*\n]+)\*\*/g, "$1")
    .replace(/__([^_\n]+)__/g, "$1")
    .replace(/(^|[^\w*])\*([^*\n]+)\*(?=[^\w*]|$)/g, "$1$2")
    .replace(/(^|[^\w_])_([^_\n]+)_(?=[^\w_]|$)/g, "$1$2")
    .replace(/\*{2,3}/g, "")
    .replace(/_{2,3}/g, "");

  return out.replace(/\u0000(\d+)\u0000/g, (_m, i: string) => blocks[Number(i)] ?? "");
}
