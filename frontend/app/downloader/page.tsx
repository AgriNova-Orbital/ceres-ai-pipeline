"use client";

import { useState } from "react";
import PageLayout from "@/components/PageLayout";
import FeedbackMessage from "@/components/FeedbackMessage";
import SubmitButton from "@/components/SubmitButton";
import JobPanel from "@/components/JobPanel";
import JobDetailCard from "@/components/JobDetailCard";
import { useApiSubmit } from "@/lib/useApiSubmit";

const actions = [
  { key: "download_all", label: "Download All", desc: "Full download from Earth Engine for the selected date range" },
  { key: "preview_export", label: "Preview Export (dry run)", desc: "Preview what would be downloaded without actually downloading" },
  { key: "refresh_inventory", label: "Refresh Inventory", desc: "Scan and update the data inventory catalog" },
];

export default function DownloaderPage() {
  const [action, setAction] = useState("preview_export");
  const [stage, setStage] = useState("1");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [limit, setLimit] = useState("4");
  const [driveFolder, setDriveFolder] = useState("");
  const [eeProject, setEeProject] = useState("");
  const [inputError, setInputError] = useState("");
  const { loading, result, error, jobId, submit, clearResult, clearError } =
    useApiSubmit();

  function handleSubmit() {
    if (action === "download_all" && !driveFolder.trim()) {
      setInputError("Drive Folder ID is required for Download All.");
      clearResult();
      clearError();
      return;
    }
    setInputError("");
    submit("/api/run/downloader", {
      action,
      stage,
      start_date: startDate,
      end_date: endDate,
      limit,
      drive_folder: driveFolder,
      ee_project: eeProject,
    });
  }

  return (
    <PageLayout
      title="Downloader"
      description="Download weekly Sentinel-2 rasters from Google Earth Engine."
    >
      <div className="bg-white rounded-lg shadow-sm border p-6 space-y-6">
        {(result || error || inputError) && (
          <FeedbackMessage
            message={result || error || inputError}
            type={result ? "success" : "error"}
            jobId={jobId || undefined}
            onClear={() => { clearResult(); clearError(); setInputError(""); }}
          />
        )}

        <div>
          <label className="block text-sm font-medium mb-2">Action</label>
          <div className="space-y-2">
            {actions.map((a) => (
              <label
                key={a.key}
                className={`flex items-start gap-3 p-3 rounded border cursor-pointer transition-colors ${
                  action === a.key
                    ? "border-primary bg-blue-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <input
                  type="radio"
                  name="action"
                  value={a.key}
                  checked={action === a.key}
                  onChange={() => setAction(a.key)}
                  className="mt-1"
                />
                <div>
                  <p className="font-medium text-sm">{a.label}</p>
                  <p className="text-xs text-gray-500">{a.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Stage" value={stage} onChange={setStage} />
          <Field label="Limit" value={limit} onChange={setLimit} />
          <Field label="Start Date" value={startDate} onChange={setStartDate} type="date" />
          <Field label="End Date" value={endDate} onChange={setEndDate} type="date" />
          <Field label="Drive Folder ID" value={driveFolder} onChange={setDriveFolder} />
          <Field label="Earth Engine Project" value={eeProject} onChange={setEeProject} />
        </div>

        <SubmitButton
          loading={loading}
          onClick={handleSubmit}
          label="Run Downloader"
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
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
      />
    </label>
  );
}
