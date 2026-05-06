import Link from "next/link";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import ThemeSwitcher from "@/components/ThemeSwitcher";
import LocaleText from "@/components/LocaleText";
import BrandLogo from "@/components/BrandLogo";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-stone-50 text-stone-900 dark:bg-stone-950 dark:text-stone-100">
      <header className="sticky top-0 z-30 border-b border-stone-200/80 bg-stone-50/95 backdrop-blur dark:border-stone-800 dark:bg-stone-950/90">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-8">
          <div className="flex items-center gap-3">
            <BrandLogo src="/logo/logo-square.png" alt="Ceres AI logo" className="h-9 w-9 rounded-md object-contain" fallback="🌾" />
            <div>
              <h1 className="text-lg font-bold tracking-tight sm:text-xl">Ceres AI</h1>
              <p className="text-xs text-stone-600 dark:text-stone-400">Geospatial ML Pipeline Platform</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ThemeSwitcher />
            <LanguageSwitcher />
            <Link href="/login" className="rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-800">
              Login
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden border-b border-stone-200 bg-gradient-to-br from-emerald-100 via-stone-50 to-amber-100 dark:border-stone-800 dark:from-emerald-950 dark:via-stone-950 dark:to-amber-950">
          <div className="pointer-events-none absolute -top-16 right-0 h-64 w-64 rounded-full bg-emerald-300/40 blur-3xl dark:bg-emerald-800/30" />
          <div className="pointer-events-none absolute bottom-0 left-10 h-52 w-52 rounded-full bg-amber-300/40 blur-3xl dark:bg-amber-900/30" />

          <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-8 sm:py-24">
            <div className="max-w-3xl space-y-6">
              <p className="inline-flex items-center rounded-full border border-emerald-300 bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 dark:border-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200">
                Ceres AI / 穀神星AI
              </p>
              <h2 className="text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
                Build crop-risk intelligence with production-ready geospatial AI.
              </h2>
              <p className="max-w-2xl text-base text-stone-700 dark:text-stone-300 sm:text-lg">
                這是公開展示首頁。登入後可進入完整操作面板，執行資料抓取、資料建置、模型訓練與評估流程。
              </p>

              <div className="flex flex-wrap gap-3">
                <Link href="/login" className="rounded-lg bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-800">
                  Sign in
                </Link>
                <Link href="/dashboard" prefetch={false} className="rounded-lg border border-stone-300 bg-white px-5 py-2.5 text-sm font-semibold text-stone-800 transition hover:border-stone-400 hover:bg-stone-100 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100 dark:hover:bg-stone-800">
                  Open Dashboard
                </Link>
              </div>
            </div>
          </div>
        </section>

        <footer className="border-t border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-950">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-sm text-stone-500 dark:text-stone-400 sm:px-8">
            <p>© {new Date().getFullYear()} Ceres AI</p>
            <div className="flex items-center gap-4">
              <Link href="/privacy" className="hover:text-emerald-700 hover:underline dark:hover:text-emerald-400">
                <LocaleText k="privacyPolicy" fallback="Privacy Policy" />
              </Link>
              <Link href="/terms" className="hover:text-emerald-700 hover:underline dark:hover:text-emerald-400">
                <LocaleText k="termsOfService" fallback="Terms of Service" />
              </Link>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}
