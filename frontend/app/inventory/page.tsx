"use client";

import { useState } from "react";
import PageLayout from "@/components/PageLayout";
import FeedbackMessage from "@/components/FeedbackMessage";
import SubmitButton from "@/components/SubmitButton";
import JobPanel from "@/components/JobPanel";
import JobDetailCard from "@/components/JobDetailCard";
import { useApiSubmit } from "@/lib/useApiSubmit";

export default function InventoryPage() {
  const { loading, result, error, jobId, submit, clearResult, clearError } =
    useApiSubmit();

  function handleRefresh() {
    submit("/api/run/downloader", { action: "refresh_inventory" });
  }

  return (
    <PageLayout
      title="Inventory"
      description="Refresh the data inventory to scan for new files and update the catalog."
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

        <SubmitButton
          loading={loading}
          onClick={handleRefresh}
          label="Refresh Inventory"
          loadingLabel="Refreshing\u2026"
        />
      </div>
      <JobDetailCard jobId={jobId} />
      <JobPanel />
    </PageLayout>
  );
}
