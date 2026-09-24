import type { PostRecord } from "../types";
import PublishButton from "./PublishButton";
import StatusBadge from "./StatusBadge";

interface Props {
  record: PostRecord;
  busy?: boolean;
  onApprove: () => void;
  onReject: () => void;
  onPublish: () => void;
  onSave: () => void;
  dirty: boolean;
  saving?: boolean;
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
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium" style={{ color: "var(--muted)" }}>
              Human review required:
            </span>
            <span className="text-xs" style={{ color: "var(--faint)" }}>
              approve to publish, or reject to discard.
            </span>
          </div>
          <span className="flex-1" />
          {!rejected && (
            <button type="button" onClick={onApprove} disabled={busy} className="btn-primary">
              ✓ Approve &amp; Publish
            </button>
          )}
          <button type="button" onClick={onReject} disabled={busy} className="btn-danger">
            ✕ Reject
          </button>
        </div>
      )}
    </div>
  );
}