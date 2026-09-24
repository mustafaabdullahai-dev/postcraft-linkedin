export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const secs = Math.round((Date.now() - then) / 1000);
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

/** Tags from the authoritative hashtag line(s) of a post body (e.g. `#ai\n#agents`). */
export function parseHashtagLine(text: string): string[] {
  const out: string[] = [];
  for (const line of (text ?? "").split(/\n+/)) {
    const stripped = line.trim();
    if (!stripped.startsWith("#")) continue;
    const tags = (stripped.match(/#[\p{L}\p{N}_]+/gu) ?? []).map((t) => t.toLowerCase());
    const contentOnly = stripped.replace(/(#[\p{L}\p{N}_]+[ \t]*)+/gu, "").trim();
    if (!contentOnly) {
      for (const t of tags) if (!out.includes(t)) out.push(t);
    }
  }
  return out;
}

const STATUS_TAGS: Record<string, string> = {
  PUBLISHED: "tag--mint",
  READY_FOR_REVIEW: "tag--sky",
  EDITED: "tag--sky",
  APPROVED: "tag--lavender",
  FAILED: "tag--rose",
  GENERATED: "tag--butter",
  REJECTED: "tag--slate",
};

export function statusColor(status: string): string {
  return STATUS_TAGS[status.toUpperCase()] ?? "tag--slate";
}

const FRIENDLY_STATUS: Record<string, string> = {
  INITIALIZED: "Draft created",
  GENERATED: "Draft generated",
  READY_FOR_REVIEW: "Needs review",
  EDITED: "Edited",
  PUBLISHING: "Publishing…",
  PUBLISHED: "LIVE",
  FAILED: "Failed",
  APPROVED: "Approved",
  NOT_APPROVED: "Awaiting approval",
  REJECTED: "Rejected",
  PENDING: "In progress",
  VALID: "Quality passed",
  INVALID: "Quality failed",
  UNVALIDATED: "Not checked",
  NOT_LOGGED: "—",
};

/** Layman-friendly label for an internal status value (e.g. READY_FOR_REVIEW → "Needs review"). */
export function humanizeStatus(status: string): string {
  return FRIENDLY_STATUS[status.toUpperCase()] ?? status.replaceAll("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

const EVENT_LABELS: Record<string, string> = {
  CREATED: "Post created",
  GENERATED: "Draft generated",
  REGENERATED_FULL: "Regenerated",
  REGENERATED_TEXT: "Draft regenerated",
  IMAGE_REGENERATED: "Image regenerated",
  EDITED: "Copy edited",
  REVISION_SAVED: "Revision saved",
  APPROVED_PUBLISHED: "Approved & published",
  APPROVED_PUBLISH_FAILED: "Publish failed at approval",
  REJECTED: "Rejected",
  PUBLISH_RETRY: "Publish attempt",
  APPROVAL_FAILED: "Publish encountered an issue",
  VALIDATED: "Quality checked",
};

/** Friendly, past-tense label for an audit event (e.g. EDITED → "Copy edited"). */
export function humanizeEvent(event: string): string {
  return EVENT_LABELS[event.toUpperCase()] ?? event.replaceAll("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

export interface Stage {
  label: string;
  pulse?: boolean;
}