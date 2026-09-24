import { humanizeStatus, statusColor } from "../utils/format";

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`tag ${statusColor(status)}`} title={status}>
      {humanizeStatus(status)}
    </span>
  );
}