import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";

const sections = [
  { title: "Admin Dashboard", desc: "System overview, workers, queue, storage", href: "/admin" },
  { title: "Jobs Monitor", desc: "All submitted and completed jobs", href: "/jobs" },
  { title: "Settings", desc: "Google OAuth, configuration", href: "/settings" },
  { title: "Data Browser", desc: "Browse raw GeoTIFFs, patches, runs, reports", href: "/data" },
  { title: "Data Ingest", desc: "Normalize and merge weekly GeoTIFFs", href: "/ingest" },
  { title: "Google Drive", desc: "Browse and download from Google Drive", href: "/drive" },
  { title: "Downloader", desc: "Download weekly Sentinel-2 rasters", href: "/downloader" },
  { title: "Build Dataset", desc: "Build staged patches from raw data", href: "/build" },
  { title: "Training", desc: "Train LSTM model", href: "/training" },
  { title: "Evaluation", desc: "Evaluate model performance", href: "/evaluation" },
  { title: "Inventory", desc: "Refresh data inventory", href: "/inventory" },
  { title: "Preview", desc: "Preview raster and patch data", href: "/preview" },
];

export default function Home() {
  return (
    <div className="min-h-screen p-8">
      <header className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-primary">Ceres AI Pipeline</h1>
          <p className="text-gray-500">Wheat Risk WebUI</p>
        </div>
        <LogoutButton />
      </header>

      <main className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {sections.map((s) => (
          <Link key={s.href} href={s.href} className="block p-6 bg-white rounded-lg shadow-sm border border-gray-200 hover:shadow-md hover:border-primary transition-all">
            <h2 className="text-lg font-semibold text-gray-900">{s.title}</h2>
            <p className="text-sm text-gray-500 mt-1">{s.desc}</p>
          </Link>
        ))}
      </main>
    </div>
  );
}
