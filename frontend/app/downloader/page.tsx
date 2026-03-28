import PageLayout from "@/components/PageLayout";
import ActionButton from "@/components/ActionButton";

export default function DownloaderPage() {
  return (
    <PageLayout title="Downloader">
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="text-lg font-semibold mb-4">Actions</h2>
        <ActionButton label="Download All" endpoint="/api/run/downloader" body={{ action: "download_all" }} />
        <ActionButton label="Refresh Inventory" endpoint="/api/run/downloader" body={{ action: "refresh_inventory" }} />
        <ActionButton label="Preview Export (dry run)" endpoint="/api/run/downloader" body={{ action: "preview_export" }} />
      </div>
    </PageLayout>
  );
}
