export type ThemeMode = "light" | "dark";

export const defaultTheme: ThemeMode = "light";

export function getStoredThemeSafe(): ThemeMode {
  if (typeof window === "undefined") return defaultTheme;
  const t = window.localStorage.getItem("ceres-theme");
  return t === "dark" || t === "light" ? t : defaultTheme;
}

export function applyTheme(theme: ThemeMode) {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", theme === "dark");
}
