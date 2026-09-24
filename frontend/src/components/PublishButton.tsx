interface Props {
  disabled?: boolean;
  busy?: boolean;
  onClick: () => void;
  label?: string;
  busyLabel?: string;
}

export default function PublishButton({ disabled, busy, onClick, label = "Publish to LinkedIn", busyLabel }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || busy}
      className="btn-primary"
      style={{ background: "var(--t-mint-d)" }}
    >
      {busy ? (
        <>
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
          {busyLabel ?? "Publishing…"}
        </>
      ) : (
        <>{(label ?? "Publish to LinkedIn")}</>
      )}
    </button>
  );
}