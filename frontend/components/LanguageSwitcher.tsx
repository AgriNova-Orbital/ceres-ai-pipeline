"use client";

import { useEffect, useState } from "react";
import { defaultLocale, getStoredLocaleSafe, type Locale } from "@/lib/i18n";

export default function LanguageSwitcher() {
  const [locale, setLocale] = useState<Locale>(defaultLocale);

  useEffect(() => {
    const current = getStoredLocaleSafe();
    setLocale(current);
  }, []);

  function toggleLocale() {
    const next: Locale = locale === "zh-TW" ? "en" : "zh-TW";
    window.localStorage.setItem("ceres-locale", next);
    setLocale(next);
    window.dispatchEvent(new CustomEvent("ceres-locale-change", { detail: { locale: next } }));
  }

  return (
    <button
      type="button"
      onClick={toggleLocale}
      aria-label="Switch language"
      className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
    >
      {locale === "zh-TW" ? "EN" : "繁中"}
    </button>
  );
}
