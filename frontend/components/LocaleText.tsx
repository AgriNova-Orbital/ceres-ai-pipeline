"use client";

import { useEffect, useState } from "react";
import { defaultLocale, getStoredLocaleSafe, translate, type Locale } from "@/lib/i18n";

export default function LocaleText({
  k,
  fallback,
  className,
}: {
  k: string;
  fallback?: string;
  className?: string;
}) {
  const [locale, setLocale] = useState<Locale>(defaultLocale);

  useEffect(() => {
    setLocale(getStoredLocaleSafe());

    const handler = (evt: Event) => {
      const custom = evt as CustomEvent<{ locale?: Locale }>;
      const next = custom?.detail?.locale;
      if (next === "en" || next === "zh-TW") setLocale(next);
      else setLocale(getStoredLocaleSafe());
    };

    window.addEventListener("ceres-locale-change", handler);
    return () => window.removeEventListener("ceres-locale-change", handler);
  }, []);

  return <span className={className}>{translate(k, locale, fallback)}</span>;
}
