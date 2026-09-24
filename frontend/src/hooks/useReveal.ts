import { useEffect } from "react";

/** Fades in every `.rv` element once when it scrolls into view (or is already visible). */
export function useReveal(dep?: unknown) {
  useEffect(() => {
    const scan = () => {
      const els = Array.from(document.querySelectorAll<HTMLElement>(".rv:not(.is-visible)"));
      if (!els.length) return undefined;
      if (!("IntersectionObserver" in window)) {
        els.forEach((el) => el.classList.add("is-visible"));
        return undefined;
      }
      const io = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              io.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.08 },
      );
      els.forEach((el) => io.observe(el));
      return io;
    };

    let io = scan();

    // Re-reveal panels that mount later (tab switches, device toggles,
    // selection changes) without needing a manual dep bump.
    let scheduled = false;
    const rescan = () => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        io?.disconnect();
        io = scan();
      });
    };
    const mo = new MutationObserver(rescan);
    mo.observe(document.body, { childList: true, subtree: true });

    return () => {
      io?.disconnect();
      mo.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dep]);
}