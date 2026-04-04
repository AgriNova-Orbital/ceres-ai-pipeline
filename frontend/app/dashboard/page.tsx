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

export default function DashboardPage() {
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
