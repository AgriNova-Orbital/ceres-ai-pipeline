import PageLayout from "@/components/PageLayout";
import ActionButton from "@/components/ActionButton";

export default function BuildPage() {
  return (
    <PageLayout title="Build Dataset">
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="text-lg font-semibold mb-4">Actions</h2>
        <ActionButton label="Build Staged Dataset" endpoint="/api/run/build" body={{ action: "build_staged" }} />
        <ActionButton label="Dry Run" endpoint="/api/run/build" body={{ action: "dry_run" }} />
      </div>
    </PageLayout>
  );
}
