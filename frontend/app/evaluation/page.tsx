"use client";

import { useState } from "react";
import PageLayout from "@/components/PageLayout";
import FeedbackMessage from "@/components/FeedbackMessage";
import SubmitButton from "@/components/SubmitButton";
import JobPanel from "@/components/JobPanel";
import JobDetailCard from "@/components/JobDetailCard";
import { useApiSubmit } from "@/lib/useApiSubmit";

export default function EvaluationPage() {
  const [summaryCsv, setSummaryCsv] = useState("runs/staged_final/summary.csv");
  const [precisionFloor, setPrecisionFloor] = useState("0.35");
  const [labelThreshold, setLabelThreshold] = useState("0.5");
  const [device, setDevice] = useState("cpu");
  const { loading, result, error, jobId, submit, clearResult, clearError } =
    useApiSubmit();

  function handleRun() {
    submit("/api/run/eval", {
      action: "run_eval",
      summary_csv: summaryCsv,
      precision_floor: Number(precisionFloor),
      label_threshold: Number(labelThreshold),
      device,
    });
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

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Summary CSV" value={summaryCsv} onChange={setSummaryCsv} />
          <Field label="Device" value={device} onChange={setDevice} />
          <Field label="Precision Floor" value={precisionFloor} onChange={setPrecisionFloor} />
          <Field label="Label Threshold" value={labelThreshold} onChange={setLabelThreshold} />
        </div>

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

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
      />
    </label>
  );
}
