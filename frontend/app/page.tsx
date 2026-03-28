import LogoutButton from "@/components/LogoutButton";

export default function Home() {
  return (
    <div className="min-h-screen p-8">
      <header className="mb-8">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-primary">Ceres AI Pipeline</h1>
            <p className="text-gray-500">Wheat Risk WebUI</p>
          </div>
          <LogoutButton />
        </div>
      </header>

      <main className="max-w-6xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Card title="Downloader" desc="Download weekly Sentinel-2 rasters" />
          <Card title="Build Dataset" desc="Build staged patches from raw data" />
          <Card title="Training" desc="Train LSTM model" />
          <Card title="Evaluation" desc="Evaluate model performance" />
          <Card title="Inventory" desc="Refresh data inventory" />
          <Card title="Preview" desc="Preview raster and patch data" />
        </div>
      </main>
    </div>
  );
}

function Card({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="p-6 bg-white rounded-lg shadow-sm border border-gray-200 hover:shadow-md transition-shadow cursor-pointer">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      <p className="text-sm text-gray-500 mt-1">{desc}</p>
    </div>
  );
}
