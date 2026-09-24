import { useState } from "react";
import type { PostRecord } from "../types";
import { formatLocalTime } from "../utils/format";
import PublishButton from "./PublishButton";
import StatusBadge from "./StatusBadge";

interface Props {
  record: PostRecord;
  busy?: boolean;
  onApprove: (scheduledAt?: string) => void;
  onReject: () => void;
  onPublish: () => void;
  onSave: () => void;
  dirty: boolean;
  saving?: boolean;
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function localInput(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function ApprovalPanel({
  record,
  busy,
  onApprove,
  onReject,
  onPublish,
  onSave,
  dirty,
  saving,
}: Props) {
  const approved = record.approval_status === "APPROVED";
  const published = record.record_status === "PUBLISHED";
  const rejected = record.review_status === "REJECTED";
  const scheduled = record.record_status === "SCHEDULED";
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [scheduleAt, setScheduleAt] = useState(() => {
    const d = new Date(Date.now() + 2 * 60 * 60 * 1000);
    return localInput(d);
  });

  if (published) {
    return (
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status="PUBLISHED" />
          <span className="text-xs" style={{ color: "var(--muted)" }}>
            Live on LinkedIn — any edit below is saved as a revision and republished as a new post.
          </span>
        </div>
        {dirty && (
          <div
            className="flex flex-wrap items-center justify-between gap-2 rounded-xl border px-3 py-2 text-sm font-medium"
            style={{ borderColor: "var(--warn-soft)", background: "var(--warn-soft)", color: "var(--warn)" }}
          >
            <span>You have unsaved edits.</span>
            <button type="button" onClick={onSave} disabled={saving} className="btn-secondary px-3 py-1 text-xs">
              {saving ? "Saving…" : "Save revision"}
            </button>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs" style={{ color: "var(--faint)" }}>
            Publish a fresh LinkedIn post from the current copy.
          </span>
          <span className="flex-1" />
          <PublishButton onClick={onPublish} busy={busy} label="Republish revision" />
        </div>
      </div>
    );
  }

  if (scheduled) {
    return (
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status="SCHEDULED" />
          <span className="text-xs" style={{ color: "var(--muted)" }}>
            This post will auto-publish {record.scheduled_at ? `on ${formatLocalTime(record.scheduled_at)}` : "soon"}.
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs" style={{ color: "var(--faint)" }}>
            Changed your mind? Publish now, or cancel the schedule and come back later.
          </span>
          <span className="flex-1" />
          <button type="button" onClick={onPublish} disabled={busy} className="btn-primary">
            Publish now instead
          </button>
          <button
            type="button"
            onClick={() => {
              if (window.confirm("Cancel the schedule? The post goes back to review.")) onReject();
            }}
            disabled={busy}
            className="btn-danger"
          >
            Cancel schedule
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {dirty && (
        <div
          className="flex flex-wrap items-center justify-between gap-2 rounded-xl border px-3 py-2 text-sm font-medium"
          style={{ borderColor: "var(--warn-soft)", background: "var(--warn-soft)", color: "var(--warn)" }}
        >
          <span>You have unsaved edits.</span>
          <button type="button" onClick={onSave} disabled={saving} className="btn-secondary px-3 py-1 text-xs">
            {saving ? "Saving…" : "Save edits"}
          </button>
        </div>
      )}

      {approved ? (
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status="APPROVED" />
          <span className="text-xs" style={{ color: "var(--muted)" }}>
            Ready to publish.
          </span>
          <span className="flex-1" />
          <PublishButton onClick={onPublish} busy={busy} />
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium" style={{ color: "var(--muted)" }}>
                Human review required:
              </span>
              <span className="text-xs" style={{ color: "var(--faint)" }}>
                publish now, schedule a time, or reject.
              </span>
            </div>
            <span className="flex-1" />
            {!rejected && (
              <button type="button" onClick={() => onApprove()} disabled={busy} className="btn-primary">
                ✓ Approve &amp; Publish
              </button>
            )}
            {!rejected && (
              <button
                type="button"
                onClick={() => {
                  setScheduleOpen((s) => !s);
                  setScheduleAt(localInput(new Date(Date.now() + 2 * 60 * 60 * 1000)));
                }}
                disabled={busy}
                className="btn-secondary"
                aria-expanded={scheduleOpen}
              >
                ⏰ Schedule
              </button>
            )}
            <button type="button" onClick={onReject} disabled={busy} className="btn-danger">
              ✕ Reject
            </button>
          </div>

          {scheduleOpen && !rejected && (
            <div className="space-y-2 rounded-xl border p-3" style={{ borderColor: "var(--accent-soft)", background: "var(--surface-1)" }}>
              <label className="label !mb-0" htmlFor="schedule-at">
                When should it go live?
              </label>
              <p className="hint">Your local time — the app publishes automatically at that moment.</p>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  id="schedule-at"
                  type="datetime-local"
                  value={scheduleAt}
                  onChange={(e) => setScheduleAt(e.target.value)}
                  className="input flex-1 !h-9 !text-xs"
                />
                <button
                  type="button"
                  onClick={() => onApprove(new Date(scheduleAt).toISOString())}
                  disabled={busy || !scheduleAt}
                  className="btn-primary"
                >
                  ✓ Approve &amp; schedule
                </button>
                <button type="button" onClick={() => setScheduleOpen(false)} disabled={busy} className="btn-ghost">
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}