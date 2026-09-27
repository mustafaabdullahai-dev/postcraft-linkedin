import { useEffect, useRef, useState } from "react";

import type { User } from "../types";
import ThemeToggle from "./ThemeToggle";

interface Props {
  user: User;
  onSignOut: () => void;
  onGuidelines: () => void;
}

/**
 * Mobile-only overflow menu: collapses the account (avatar, name, sign out) and
 * the theme switch behind a single hamburger so the top bar stays clean.
 */
export default function MobileMenu({ user, onSignOut, onGuidelines }: Props) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open]);

  const initials = user.name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  const secondary = user.is_guest ? "Guest account" : user.email || user.headline || "";

  return (
    <div className="relative shrink-0 lg:hidden" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Menu"
        title="Menu"
        className="btn-ghost !px-2.5 !py-2"
      >
        <svg
          viewBox="0 0 16 16"
          className="h-5 w-5"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.7}
          strokeLinecap="round"
          aria-hidden="true"
        >
          {open ? (
            <>
              <path d="M3.5 3.5l9 9" />
              <path d="M12.5 3.5l-9 9" />
            </>
          ) : (
            <>
              <path d="M2.5 4h11" />
              <path d="M2.5 8h11" />
              <path d="M2.5 12h11" />
            </>
          )}
        </svg>
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-2 w-72 max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-2xl border p-1.5 shadow-lg"
          style={{ background: "var(--surface)", borderColor: "var(--line)" }}
        >
          <div className="flex items-center gap-3 rounded-xl px-2.5 py-2.5">
            {user.picture_url ? (
              <img src={user.picture_url} alt="" className="h-10 w-10 shrink-0 rounded-full" />
            ) : (
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[13px] font-bold text-white"
                style={{ background: "linear-gradient(135deg,#2f6fed,#7b2ff7)" }}
                aria-hidden="true"
              >
                {initials}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold" style={{ color: "var(--ink)" }}>
                {user.name}
              </p>
              {secondary ? (
                <p className="truncate text-[11px]" style={{ color: "var(--faint)" }}>
                  {secondary}
                </p>
              ) : null}
            </div>
          </div>

          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onGuidelines();
            }}
            className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2.5 text-left text-xs font-semibold transition hover:bg-[var(--surface-2)]"
            style={{ color: "var(--ink)" }}
          >
            <span className="w-4 shrink-0 text-center" aria-hidden="true">
              ✓
            </span>
            LinkedIn guidelines
          </button>

          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
            className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2.5 text-left text-xs font-semibold transition hover:bg-[var(--bad-soft)]"
            style={{ color: "var(--bad)" }}
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 fill-current" aria-hidden="true">
              <path d="M10 3H5.5A2.5 2.5 0 0 0 3 5.5v13A2.5 2.5 0 0 0 5.5 21H10v-2H5.5a.5.5 0 0 1-.5-.5v-13a.5.5 0 0 1 .5-.5H10V3zm5.6 4.4L14.2 8.8l2.2 2.2H8v2h8.4l-2.2 2.2 1.4 1.4L20 12l-4.4-4.6z" />
            </svg>
            Sign out
          </button>

          <div className="mx-2 my-1 h-px" style={{ background: "var(--line)" }} />

          <div className="flex items-center justify-between gap-2 px-2.5 pb-1.5 pt-1">
            <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: "var(--faint)" }}>
              Theme
            </span>
            <ThemeToggle />
          </div>
        </div>
      ) : null}
    </div>
  );
}
