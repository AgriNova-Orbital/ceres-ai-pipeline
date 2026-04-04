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
      className="rounded-md border border-white/20 bg-white/5 px-2.5 py-1.5 text-xs font-semibold text-white transition hover:bg-white/10"
    >
      {locale === "zh-TW" ? "EN" : "繁中"}
    </button>
  );
}
