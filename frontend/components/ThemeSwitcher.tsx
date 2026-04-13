"use client";

import { useEffect, useState } from "react";
import { applyTheme, defaultTheme, getStoredThemeSafe, type ThemeMode } from "@/lib/theme";

export default function ThemeSwitcher() {
  const [theme, setTheme] = useState<ThemeMode>(defaultTheme);

  useEffect(() => {
    const current = getStoredThemeSafe();
    setTheme(current);
    applyTheme(current);
  }, []);

  function toggleTheme() {
    const next: ThemeMode = theme === "light" ? "dark" : "light";
    window.localStorage.setItem("ceres-theme", next);
    setTheme(next);
    applyTheme(next);
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label="Switch theme"
      className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
    >
      {theme === "light" ? "🌙 Dark" : "☀️ Light"}
    </button>
  );
}
