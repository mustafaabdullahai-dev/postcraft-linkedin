import type { PostRecord, User } from "../types";

const AVATAR_GRADIENTS = [
  "linear-gradient(135deg,#2f6fed,#7b2ff7)",
  "linear-gradient(135deg,#e8643f,#d62c5a)",
  "linear-gradient(135deg,#0f9d74,#0b6fb8)",
];

function avatarGradient(id: string) {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) % 100000;
  return AVATAR_GRADIENTS[h % AVATAR_GRADIENTS.length];
}

function initials(name: string) {
  return name
    .split(" ")
    .map((w) => w[0])
    .filter(Boolean)
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function rich(text: string) {
  const parts = text.split("**");
  if (parts.length === 1) return text;
  return parts.map((p, i) =>
    i % 2 === 1 ? (
      <strong key={i} className="font-bold text-[var(--ink)]">
        {p}
      </strong>
    ) : (
      <span key={`${i}-p`}>{p}</span>
    ),
  );
}

function paragraphize(text: string) {
  return text
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p, i) => {
      const tags = p.match(/#[\w]+/g);
      if (tags && tags.join("") === p.replace(/\s/g, "") && p.trimStart().startsWith("#")) {
        return (
          <div key={i} className="flex flex-wrap gap-2 pt-2">
            {tags.map((t) => (
              <span key={t} className="text-sm font-semibold text-[var(--accent)]">
                {t}
              </span>
            ))}
          </div>
        );
      }
      if (p.startsWith("•")) {
        return (
          <div key={i} className="flex gap-2 pt-2.5 text-[var(--ink-soft)]">
            <span className="font-bold text-[var(--accent)]" aria-hidden="true">
              •
            </span>
            <span>
              {rich(p.slice(1).trim())}
            </span>
          </div>
        );
      }
      return (
        <p key={i} className={i === 0 ? "pt-2" : "pt-3"}>
          {rich(p)}
        </p>
      );
    });
}

interface Props {
  record: PostRecord;
  user?: User | null;
  variant?: "mobile" | "desktop";
}

export default function PostPreview({ record, user, variant = "desktop" }: Props) {
  const m = variant === "mobile";
  const text = record.final_post ?? record.generated_post ?? "";
  const name = user?.name ?? "Guest";
  const headline = user?.headline ?? "PostCraft — AI content agent";
  const picture = user?.picture_url ?? "";
  const showImage = Boolean(record.image_url);
  const followers = 1450 + ((Number(record.record_id.replace(/[^\d]/g, "").slice(-2)) || 0) * 37) % 900;

return (
    <div
      className="mx-auto w-full overflow-hidden rounded-xl border border-[var(--line-2)] bg-[var(--surface)] text-[var(--ink)] shadow-[0_1px_2px_rgba(34,31,27,0.05)]"
      style={m ? {} : { maxWidth: 620 }}
    >
      <div className={m ? "flex items-start gap-2.5 p-3" : "flex items-start gap-3 p-4"}>
        {picture ? (
          <img
            src={picture}
            alt={name}
            className={m ? "h-10 w-10 shrink-0 rounded-full object-cover" : "h-12 w-12 shrink-0 rounded-full object-cover"}
          />
        ) : (
          <div
            className={
              m
                ? "flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
                : "flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
            }
            style={{ background: avatarGradient(record.record_id) }}
          >
            {initials(name)}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1 font-semibold leading-tight">
            <span className="truncate">{name}</span>
            <svg viewBox="0 0 16 16" className={m ? "h-3.5 w-3.5 shrink-0 fill-[#2f6fed]" : "h-4 w-4 shrink-0 fill-[#2f6fed]"} aria-label="verified">
              <title>Verified</title>
              <path d="M8 0l1.6 1.6 2.3-.4 1.2 2 2 1.2-.4 2.3L16 8l-1.6 1.6.4 2.3-2 1.2-1.2 2-2.3-.4L8 16l-1.6-1.6-2.3.4-1.2-2-2-1.2.4-2.3L0 8l1.6-1.6-.4-2.3 2-1.2 1.2-2 2 2.3.4z" />
            </svg>
          </div>
          <div className={m ? "truncate text-[13px] text-[var(--muted)]" : "truncate text-sm text-[var(--muted)]"}>{headline}</div>
          <div className="flex items-center gap-1 text-xs text-[var(--faint)]">
            <span>{record.post_type}</span>
            <span aria-hidden="true">·</span>
            <span>1d</span>
            {!m && (
              <>
                <span aria-hidden="true">·</span>
                <span className="rounded bg-[var(--surface-2)] px-2 py-0.5 font-medium">👥 {followers} followers</span>
              </>
            )}
          </div>
        </div>
        {m ? (
          <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0 fill-[var(--faint)]" aria-label="More">
            <circle cx="5" cy="12" r="1.6" />
            <circle cx="12" cy="12" r="1.6" />
            <circle cx="19" cy="12" r="1.6" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0 fill-[#1c7fd4]" aria-label="LinkedIn">
            <path d="M20.5 4.6c-1.4.7-2.8 1.1-4.3 1.3A4.5 4.5 0 0 0 13 3.5c-2 0-3.7 1.4-4.2 3.3a4.4 4.4 0 0 1 1.9-3v.7c-1.7.5-2.9 2-3 3.8v.6a4.5 4.5 0 0 1-.9-4.3 4.5 4.5 0 0 0 3.2 4.3c-.4 0-.8-.1-1.2-.2a4.5 4.5 0 0 0 3.9 3.1 4.5 4.5 0 0 1-4 1.2 6.6 6.6 0 0 0 3.5 1.2c4.9 0 7.5-4 7.5-7.5l0-.3c.5-.4.9-.9 1.3-1.4-.5.2-1 .4-1.5.4-.5 0-1.1-.2-1.5-.5z" />
          </svg>
        )}
      </div>

      {showImage && (
        <div className="border-y border-[var(--line)]">
          {record.image_url?.startsWith("data:image/svg") ? (
            <iframe
              title="post image"
              src={record.image_url}
              className={m ? "h-48 w-full border-0" : "h-64 w-full border-0"}
              sandbox=""
              scrolling="no"
            />
          ) : (
            <img src={record.image_url!} alt="post" className={m ? "max-h-64 w-full object-cover" : "max-h-96 w-full object-cover"} />
          )}
        </div>
      )}

      <div className={m ? "break-words px-3 pb-2 text-sm leading-relaxed" : "break-words px-4 pb-2 text-[15px] leading-relaxed"}>
        {paragraphize(text)}
      </div>

      <div className={m ? "px-3 pb-2.5 text-xs text-[var(--faint)]" : "px-4 pb-3 text-xs text-[var(--faint)]"}>
        <span className="font-medium text-[var(--muted)]">
          {2 + (Number(record.record_id.replace(/[^\d]/g, "").slice(-2)) || 0)} reactions ·{" "}
          {(1 + (Number(record.record_id.replace(/[^\d]/g, "").slice(-1)) || 0))} comments ·{" "}
          {0 + (Number(record.record_id.replace(/[^\d]/g, "").slice(0, 1)) || 0)} reposts
        </span>
      </div>

      <div
        className={
          m
            ? "mx-3 mb-3 grid grid-cols-3 border-t border-[var(--line)] pt-2.5 text-xs font-semibold"
            : "mx-4 mb-3 flex items-center justify-between border-t border-[var(--line)] pt-2 text-xs font-semibold"
        }
      >
        <span className="flex items-center gap-1 text-[var(--muted)]">
          <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current" aria-hidden="true">
            <path d="M7 12l3 3 7-7" />
          </svg>
          Like
        </span>
        <span className="flex items-center gap-1 text-[var(--muted)]">
          <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current" aria-hidden="true">
            <path d="M6 5h12a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1h-3l-3 3-3-3H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" />
          </svg>
          Comment
        </span>
        <span className="flex items-center gap-1 text-[var(--muted)]">
          <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current" aria-hidden="true">
            <path d="M17 3l5 9-5 9H7l-5-9 5-9z" />
          </svg>
          {record.priority}
        </span>
      </div>
    </div>
  );
}