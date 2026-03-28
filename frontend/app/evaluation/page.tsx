import PageLayout from "@/components/PageLayout";
import ActionButton from "@/components/ActionButton";

export default function EvaluationPage() {
  return (
    <PageLayout title="Evaluation">
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="text-lg font-semibold mb-4">Actions</h2>
        <ActionButton label="Run Evaluation" endpoint="/api/run/eval" body={{ action: "run_eval" }} />
      </div>
    </PageLayout>
  );
}
