import PageLayout from "@/components/PageLayout";
import ActionButton from "@/components/ActionButton";

export default function InventoryPage() {
  return (
    <PageLayout title="Inventory">
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="text-lg font-semibold mb-4">Actions</h2>
        <ActionButton label="Refresh Inventory" endpoint="/api/run/downloader" body={{ action: "refresh_inventory" }} />
      </div>
    </PageLayout>
  );
}
