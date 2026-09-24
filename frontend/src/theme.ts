export type ThemeMode = "light" | "dark" | "system";

const KEY = "li_theme";

export function systemTheme(): "light" | "dark" {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function resolveTheme(mode: ThemeMode): "light" | "dark" {
  return mode === "system" ? systemTheme() : mode;
}

export function applyTheme(mode: ThemeMode): void {
  const theme = resolveTheme(mode);
  document.documentElement.dataset.theme = theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "dark" ? "#121110" : "#fbfaf6");
}

export function getStoredTheme(): ThemeMode {
  try {
    const v = localStorage.getItem(KEY);
    return v === "dark" || v === "light" || v === "system" ? v : "system";
  } catch {
    return "system";
  }
}

export function storeTheme(mode: ThemeMode): void {
  localStorage.setItem(KEY, mode);
  applyTheme(mode);
}

export function initTheme(): void {
  applyTheme(getStoredTheme());
}