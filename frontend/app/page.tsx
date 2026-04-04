import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";
import LanguageSwitcher from "@/components/LanguageSwitcher";
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
    color: "from-slate-500 to-gray-500",
    sections: [{ title: "Settings", desc: "Google OAuth, configuration", href: "/settings", step: 1 }],
  },
  {
    label: "Data Acquisition",
    icon: "⬇",
    color: "from-sky-500 to-cyan-500",
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
    color: "from-violet-500 to-fuchsia-500",
    sections: [
      { title: "Training", desc: "Configure and run LSTM model training", href: "/training", step: 7 },
      { title: "Evaluation", desc: "Evaluate model performance and metrics", href: "/evaluation", step: 8 },
    ],
  },
  {
    label: "Tools & Monitoring",
    icon: "📊",
    color: "from-emerald-500 to-teal-500",
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
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/70 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-8">
          <div className="flex items-center gap-3">
            <BrandLogo src="/logo/logo-square.png" alt="Ceres AI logo" className="h-9 w-9 rounded-md object-contain" fallback="🌾" />
            <div>
              <h1 className="text-xl font-bold tracking-tight sm:text-2xl">Ceres AI Pipeline</h1>
              <p className="mt-0.5 text-xs text-slate-300 sm:text-sm">Wheat Risk Assessment · Geospatial ML Pipeline</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            <LogoutButton />
          </div>
        </div>
      </header>

      <main className="relative mx-auto max-w-6xl space-y-8 overflow-hidden px-4 py-8 sm:px-8 sm:py-10">
        <div className="pointer-events-none absolute -top-20 -left-12 h-64 w-64 rounded-full bg-sky-500/20 blur-3xl motion-safe:animate-floatSlow" />
        <div className="pointer-events-none absolute top-20 right-0 h-72 w-72 rounded-full bg-violet-500/20 blur-3xl motion-safe:animate-floatFast" />

        <section className="relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-slate-900 via-slate-900 to-slate-800 p-6 shadow-2xl sm:p-8">
          <div className="relative z-10 max-w-3xl">
            <div className="mb-3 flex items-center gap-3">
              <BrandLogo src="/logo/logo.png" alt="Ceres AI wordmark" className="h-8 w-auto object-contain" fallback="Ceres AI" />
              <p className="inline-flex rounded-full border border-cyan-400/30 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-300">
                Ceres AI / 穀神星AI
              </p>
            </div>
            <h2 className="text-2xl font-semibold leading-tight sm:text-3xl">一站式農業遙測 AI 工作台</h2>
            <p className="mt-3 text-sm text-slate-300 sm:text-base">
              從資料抓取、預處理、建模訓練到評估監控，快速完成端到端 pipeline。
            </p>
            <div className="mt-5">
              <p className="mb-2 text-xs uppercase tracking-wider text-slate-400">
                <LocaleText k="quickActions" fallback="Quick Actions" />
              </p>
              <div className="flex flex-wrap gap-3">
                <Link href="/training" className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400">
                  <LocaleText k="startTraining" fallback="Start Training" />
                </Link>
                <Link href="/jobs" className="rounded-lg border border-white/20 bg-white/5 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/10">
                  <LocaleText k="viewJobs" fallback="View Jobs" />
                </Link>
                <Link href="/settings" className="rounded-lg border border-white/20 bg-white/5 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/10">
                  <LocaleText k="openSettings" fallback="Open Settings" />
                </Link>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-6">
          {groups.map((group, groupIndex) => (
            <div key={group.label} className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">{group.icon}</span>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 sm:text-sm">{group.label}</h3>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                {group.sections.map((s, idx) => {
                  const delay = `${groupIndex * 90 + idx * 60}ms`;
                  return (
                    <Link
                      key={s.href}
                      href={s.href}
                      style={{ animationDelay: delay }}
                      className="group motion-safe:animate-cardIn rounded-xl border border-white/10 bg-white/[0.03] p-5 shadow-lg backdrop-blur transition hover:-translate-y-1 hover:border-white/25 hover:bg-white/[0.06]"
                    >
                      <div className="mb-3 flex items-start justify-between gap-3">
                        <h4 className="text-base font-semibold text-white transition-colors group-hover:text-cyan-300">{s.title}</h4>
                        {s.step > 0 ? (
                          <span className={`rounded-full bg-gradient-to-r ${group.color} px-2 py-0.5 text-xs font-semibold text-white shadow`}>
                            Step {s.step}
                          </span>
                        ) : (
                          <span className="rounded-full border border-white/20 px-2 py-0.5 text-xs text-slate-300">Tool</span>
                        )}
                      </div>
                      <p className="text-sm leading-6 text-slate-300">{s.desc}</p>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </section>

        <footer className="border-t border-white/10 pt-5 text-sm text-slate-300">
          <div className="flex flex-wrap items-center gap-4">
            <Link href="/privacy" className="hover:text-cyan-300 hover:underline">
              <LocaleText k="privacyPolicy" fallback="Privacy Policy" />
            </Link>
            <Link href="/terms" className="hover:text-cyan-300 hover:underline">
              <LocaleText k="termsOfService" fallback="Terms of Service" />
            </Link>
          </div>
        </footer>
      </main>

      <style jsx global>{`
        @keyframes cardIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes floatSlow {
          0%,
          100% {
            transform: translate(0, 0);
          }
          50% {
            transform: translate(12px, -10px);
          }
        }

        @keyframes floatFast {
          0%,
          100% {
            transform: translate(0, 0);
          }
          50% {
            transform: translate(-14px, 10px);
          }
        }

        .animate-cardIn {
          animation: cardIn 480ms ease both;
        }

        .animate-floatSlow {
          animation: floatSlow 9s ease-in-out infinite;
        }

        .animate-floatFast {
          animation: floatFast 7s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}
