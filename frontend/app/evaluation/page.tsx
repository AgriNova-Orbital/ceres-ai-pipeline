"use client";

import { useState } from "react";
import PageLayout from "@/components/PageLayout";
import JobPanel from "@/components/JobPanel";

export default function EvaluationPage() {
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleRun() {
    setLoading(true); setResult("");
    try {
      const res = await fetch("/api/run/eval", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "run_eval" }) });
      const data = await res.json();
      setResult(res.ok ? `Queued: ${data.job_id}` : `Error: ${data.error}`);
    } catch { setResult("Connection error"); }
    setLoading(false);
  }

  return (
    <PageLayout title="Evaluation">
      <div className="bg-white rounded-lg shadow-sm border p-6 space-y-6">
        <p className="text-sm text-gray-600">Run model evaluation to generate metrics and performance charts.</p>
        <div>
          <button onClick={handleRun} disabled={loading} className="px-6 py-2 bg-primary text-white rounded-md hover:bg-primary-dark disabled:opacity-50 text-sm font-medium">
            {loading ? "Submitting..." : "Run Evaluation"}
          </button>
          {result && <p className={`mt-2 text-sm ${result.startsWith("Error") ? "text-red-600" : "text-green-600"}`}>{result}</p>}
        </div>
      </div>
      <JobPanel />
    </PageLayout>
  );
}
