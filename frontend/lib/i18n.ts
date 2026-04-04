export type Locale = "en" | "zh-TW";

export const defaultLocale: Locale = "zh-TW";

export const dictionaries: Record<Locale, Record<string, string>> = {
  en: {
    home: "Home",
    privacyPolicy: "Privacy Policy",
    termsOfService: "Terms of Service",
    backHome: "Back to Home",
    quickActions: "Quick Actions",
    startTraining: "Start Training",
    viewJobs: "View Jobs",
    openSettings: "Open Settings",
  },
  "zh-TW": {
    home: "首頁",
    privacyPolicy: "隱私權政策",
    termsOfService: "服務條款",
    backHome: "返回首頁",
    quickActions: "快捷操作",
    startTraining: "開始訓練",
    viewJobs: "查看任務",
    openSettings: "開啟設定",
  },
};

export function getStoredLocaleSafe(): Locale {
  if (typeof window === "undefined") return defaultLocale;
  const val = window.localStorage.getItem("ceres-locale");
  return val === "en" || val === "zh-TW" ? val : defaultLocale;
}

export function translate(key: string, locale: Locale, fallback?: string): string {
  return dictionaries[locale]?.[key] ?? fallback ?? key;
}
