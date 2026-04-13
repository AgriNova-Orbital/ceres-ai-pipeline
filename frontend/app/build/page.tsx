"use client";

import { useState } from "react";
import PageLayout from "@/components/PageLayout";
import FeedbackMessage from "@/components/FeedbackMessage";
import SubmitButton from "@/components/SubmitButton";
import JobPanel from "@/components/JobPanel";
import { useApiSubmit } from "@/lib/useApiSubmit";

export default function BuildPage() {
  const [action, setAction] = useState("build_level");
  const [level, setLevel] = useState("1");
  const [rawDir, setRawDir] = useState("data/raw/france_2025_weekly");
  const [maxPatches, setMaxPatches] = useState("12000");
  const { loading, result, error, jobId, submit, clearResult, clearError } =
    useApiSubmit();

  function handleSubmit() {
    submit("/api/run/build", { action, level, raw_dir: rawDir, max_patches: maxPatches });
  }

  return (
    <PageLayout
      title="Build Dataset"
      description="Build staged patch datasets from raw GeoTIFF data at different resolution levels."
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

        <div>
          <label className="block text-sm font-medium mb-2">Action</label>
          <div className="space-y-2">
            {[
              { k: "build_level", l: "Build Level Dataset", d: "Build staged patches for selected level" },
              { k: "dry_run", l: "Dry Run", d: "Preview what would be built without writing files" },
            ].map((a) => (
              <label
                key={a.k}
                className={`flex items-start gap-3 p-3 rounded border cursor-pointer transition-colors ${
                  action === a.k
                    ? "border-primary bg-blue-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <input
                  type="radio"
                  name="action"
                  checked={action === a.k}
                  onChange={() => setAction(a.k)}
                  className="mt-1"
                />
                <div>
                  <p className="font-medium text-sm">{a.l}</p>
                  <p className="text-xs text-gray-500">{a.d}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-sm font-medium text-gray-700">Level</span>
            <select
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
            >
              <option value="1">Level 1 (64px)</option>
              <option value="2">Level 2 (128px)</option>
              <option value="4">Level 4 (256px)</option>
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-700">Max Patches</span>
            <input
              value={maxPatches}
              onChange={(e) => setMaxPatches(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
            />
          </label>
          <label className="block col-span-2">
            <span className="text-sm font-medium text-gray-700">Raw Data Directory</span>
            <input
              value={rawDir}
              onChange={(e) => setRawDir(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
            />
          </label>
        </div>

        <div>
          <SubmitButton
            loading={loading}
            onClick={handleSubmit}
            label="Run Build"
            loadingLabel="Submitting\u2026"
          />
        </div>
      </div>
      <JobPanel />
    </PageLayout>
  );
}
