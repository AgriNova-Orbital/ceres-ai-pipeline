import PageLayout from "@/components/PageLayout";
import ActionButton from "@/components/ActionButton";

export default function TrainingPage() {
  return (
    <PageLayout title="Training">
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="text-lg font-semibold mb-4">Actions</h2>
        <ActionButton label="Start Training" endpoint="/api/run/train" body={{ action: "run_matrix" }} />
        <ActionButton label="Dry Run" endpoint="/api/run/train" body={{ action: "dry_run" }} />
      </div>
    </PageLayout>
  );
}
