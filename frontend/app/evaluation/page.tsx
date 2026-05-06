"use client";

import { useState } from "react";
import PageLayout from "@/components/PageLayout";
import FeedbackMessage from "@/components/FeedbackMessage";
import SubmitButton from "@/components/SubmitButton";
import JobPanel from "@/components/JobPanel";
import JobDetailCard from "@/components/JobDetailCard";
import { useApiSubmit } from "@/lib/useApiSubmit";

export default function EvaluationPage() {
  const { loading, result, error, jobId, submit, clearResult, clearError } =
    useApiSubmit();

  function handleRun() {
    submit("/api/run/eval", { action: "run_eval" });
  }

  return (
    <PageLayout
      title="Evaluation"
      description="Run model evaluation to generate performance metrics and charts."
    >
      <div className="bg-white rounded-lg shadow-sm border p-6 space-y-6">
        {(result || error) && (
          <FeedbackMessage
            message={result || error}
            type={result ? "success" : "error"}
            jobId={jobId || undefined}
            onClear={() => { clearResult(); clearError(); }}
          />
        )}

        <p className="text-sm text-gray-600">
          This will evaluate all trained models and generate metrics including RMSE, MAE, and R² scores.
        </p>

        <SubmitButton
          loading={loading}
          onClick={handleRun}
          label="Run Evaluation"
          loadingLabel="Submitting\u2026"
        />
      </div>
      <JobDetailCard jobId={jobId} />
      <JobPanel />
    </PageLayout>
  );
}
