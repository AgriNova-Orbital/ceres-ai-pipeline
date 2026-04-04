import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import ThemeSwitcher from "@/components/ThemeSwitcher";
import LocaleText from "@/components/LocaleText";
import BrandLogo from "@/components/BrandLogo";

interface Section {
  title: string;
  desc: string;
  href: string;
  step: number;
}

interface PipelineGroup {
  label: string;
  icon: string;
  color: string;
  sections: Section[];
}

const groups: PipelineGroup[] = [
  {
    label: "Setup & Configuration",
    icon: "⚙",
    color: "from-stone-500 to-zinc-500",
    sections: [{ title: "Settings", desc: "Google OAuth, configuration", href: "/settings", step: 1 }],
  },
  {
    label: "Data Acquisition",
    icon: "⬇",
    color: "from-emerald-600 to-teal-600",
    sections: [
      { title: "Google Drive", desc: "Browse and download from Google Drive", href: "/drive", step: 2 },
      { title: "Downloader", desc: "Download weekly Sentinel-2 rasters from Earth Engine", href: "/downloader", step: 3 },
    ],
  },
  {
    label: "Data Processing",
    icon: "🧩",
    color: "from-amber-500 to-orange-500",
    sections: [
      { title: "Data Ingest", desc: "Normalize and merge weekly GeoTIFFs", href: "/ingest", step: 4 },
      { title: "Data Browser", desc: "Browse raw GeoTIFFs, patches, runs, reports", href: "/data", step: 5 },
      { title: "Build Dataset", desc: "Build staged patches from raw data", href: "/build", step: 6 },
    ],
  },
  {
    label: "Model Training",
    icon: "🧠",
    color: "from-lime-600 to-emerald-600",
    sections: [
      { title: "Training", desc: "Configure and run LSTM model training", href: "/training", step: 7 },
      { title: "Evaluation", desc: "Evaluate model performance and metrics", href: "/evaluation", step: 8 },
    ],
  },
  {
    label: "Tools & Monitoring",
    icon: "📊",
    color: "from-cyan-700 to-emerald-700",
    sections: [
      { title: "Admin Dashboard", desc: "System overview, workers, queue, storage", href: "/admin", step: 0 },
      { title: "Jobs Monitor", desc: "All submitted and completed jobs", href: "/jobs", step: 0 },
      { title: "Inventory", desc: "Refresh data inventory catalog", href: "/inventory", step: 0 },
      { title: "Preview", desc: "Preview raster and patch data as images", href: "/preview", step: 0 },
    ],
  },
];

export default function Home() {
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
            <LogoutButton />
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
                Build crop-risk intelligence
                <br className="hidden sm:block" />
                with production-ready geospatial AI.
              </h2>
              <p className="max-w-2xl text-base text-stone-700 dark:text-stone-300 sm:text-lg">
                從資料抓取、前處理、模型訓練到評估分析，一個平台完成端到端流程，讓你可以快速 demo，也能穩定上線。
              </p>

              <div className="flex flex-wrap gap-3">
                <Link href="/training" className="rounded-lg bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-800">
                  <LocaleText k="startTraining" fallback="Start Training" />
                </Link>
                <Link href="/jobs" className="rounded-lg border border-stone-300 bg-white px-5 py-2.5 text-sm font-semibold text-stone-800 transition hover:border-stone-400 hover:bg-stone-100 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100 dark:hover:bg-stone-800">
                  <LocaleText k="viewJobs" fallback="View Jobs" />
                </Link>
                <Link href="/settings" className="rounded-lg border border-stone-300 bg-white px-5 py-2.5 text-sm font-semibold text-stone-800 transition hover:border-stone-400 hover:bg-stone-100 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100 dark:hover:bg-stone-800">
                  <LocaleText k="openSettings" fallback="Open Settings" />
                </Link>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-stone-200 bg-stone-100/70 dark:border-stone-800 dark:bg-stone-900/40">
          <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-6 text-sm sm:grid-cols-3 sm:px-8">
            <div className="rounded-lg border border-stone-200 bg-white p-4 dark:border-stone-700 dark:bg-stone-900">⚡ Fast pipeline orchestration</div>
            <div className="rounded-lg border border-stone-200 bg-white p-4 dark:border-stone-700 dark:bg-stone-900">🔒 OAuth-ready secure access</div>
            <div className="rounded-lg border border-stone-200 bg-white p-4 dark:border-stone-700 dark:bg-stone-900">📈 End-to-end training visibility</div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl space-y-8 px-4 py-12 sm:px-8 sm:py-16">
          {groups.map((group) => (
            <div key={group.label} className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">{group.icon}</span>
                <h3 className="text-sm font-semibold uppercase tracking-wider text-stone-500 dark:text-stone-400">{group.label}</h3>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                {group.sections.map((s) => (
                  <Link
                    key={s.href}
                    href={s.href}
                    className="group rounded-xl border border-stone-200 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-md dark:border-stone-700 dark:bg-stone-900 dark:hover:border-emerald-700"
                  >
                    <div className="mb-2 flex items-start justify-between gap-3">
                      <h4 className="text-base font-semibold transition group-hover:text-emerald-700 dark:group-hover:text-emerald-400">{s.title}</h4>
                      {s.step > 0 ? (
                        <span className={`rounded-full bg-gradient-to-r ${group.color} px-2 py-0.5 text-xs font-semibold text-white`}>
                          Step {s.step}
                        </span>
                      ) : (
                        <span className="rounded-full border border-stone-300 px-2 py-0.5 text-xs text-stone-500 dark:border-stone-600 dark:text-stone-300">Tool</span>
                      )}
                    </div>
                    <p className="text-sm text-stone-600 dark:text-stone-300">{s.desc}</p>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </section>

        <section className="mx-auto max-w-7xl px-4 pb-10 sm:px-8 sm:pb-14">
          <div className="rounded-2xl bg-gradient-to-r from-emerald-800 to-amber-700 px-6 py-8 text-white shadow-lg sm:px-10">
            <h3 className="text-2xl font-bold tracking-tight">Ready to run your full pipeline?</h3>
            <p className="mt-2 text-sm text-emerald-100 sm:text-base">Use the dashboard flow to ingest, train, evaluate, and publish results with traceable jobs.</p>
            <div className="mt-5 flex flex-wrap gap-3">
              <Link href="/build" className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-emerald-800 transition hover:bg-emerald-50">Build Dataset</Link>
              <Link href="/evaluation" className="rounded-lg border border-white/50 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/10">Run Evaluation</Link>
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
