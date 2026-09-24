import type { CSSProperties } from "react";

interface Props {
  className?: string;
  style?: CSSProperties;
}

export default function Skeleton({ className = "", style }: Props) {
  return <div className={`skeleton ${className}`} style={style} aria-hidden="true" />;
}