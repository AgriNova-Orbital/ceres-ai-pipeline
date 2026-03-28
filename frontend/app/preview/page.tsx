import PageLayout from "@/components/PageLayout";

export default function PreviewPage() {
  return (
    <PageLayout title="Preview">
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <p className="text-gray-500">
          Use the preview API endpoints to view raster and patch data.
        </p>
        <div className="mt-4 space-y-2 text-sm text-gray-600">
          <p><code className="bg-gray-100 px-2 py-1 rounded">GET /api/preview/raw?path=...</code></p>
          <p><code className="bg-gray-100 px-2 py-1 rounded">GET /api/preview/patch?path=...</code></p>
        </div>
      </div>
    </PageLayout>
  );
}
