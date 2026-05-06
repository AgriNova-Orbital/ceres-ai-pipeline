"use client";

import { useEffect, useState } from "react";
import PageLayout from "@/components/PageLayout";
import { readApiResponse } from "@/lib/api-response";

interface DatasetStatus {
  path: string;
  total_files: number;
  total_groups: number;
  canonical: number;
  needs_normalize: number;
  needs_merge: number;
}

export default function IngestPage() {
  const [datasets, setDatasets] = useState<Record<string, DatasetStatus>>({});
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState<
    Record<string, { merged: number; normalized: number; failed: number; logs: string[] }>
  >({});
  const [running, setRunning] = useState<Record<string, boolean>>({});
  const [scanError, setScanError] = useState("");

  async function loadStatus() {
    setLoading(true);
    setScanError("");
    try {
      const res = await fetch("/api/ingest/status");
      const response = await readApiResponse(res, "Failed to load dataset status");
      if (!response.ok) {
        setScanError(response.error);
        return;
      }
      setDatasets((response.data.datasets as Record<string, DatasetStatus> | undefined) || {});
    } catch {
      setScanError("Failed to load dataset status. Please check the server connection.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStatus();
  }, []);

  async function handleIngest(name: string) {
    setRunning((p) => ({ ...p, [name]: true }));
    setResults((p) => ({
      ...p,
      [name]: { merged: 0, normalized: 0, failed: 0, logs: ["Submitting job..."] },
    }));
    try {
      const res = await fetch("/api/run/downloader", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "refresh_inventory",
          raw_dir: `data/raw/${name}`,
        }),
      });
      const response = await readApiResponse(res, "Failed to submit ingest job");
      const jobId = response.ok && typeof response.data.job_id === "string" ? response.data.job_id : null;
      if (jobId) {
        setResults((p) => ({
          ...p,
          [name]: {
            merged: 0,
            normalized: 0,
            failed: 0,
            logs: [`Job queued: ${jobId}`, "Monitor progress on the Jobs page."],
          },
        }));
      } else {
        setResults((p) => ({
          ...p,
          [name]: {
            merged: 0,
            normalized: 0,
            failed: 1,
            logs: [`Error: ${response.ok ? "Missing job id" : response.error}`],
          },
        }));
      }
    } catch {
      setResults((p) => ({
        ...p,
        [name]: {
          merged: 0,
          normalized: 0,
          failed: 1,
          logs: ["Connection error. Please check if the server is running."],
        },
      }));
    }
    setRunning((p) => ({ ...p, [name]: false }));
  }

  if (loading) {
    return (
      <PageLayout title="Data Ingest">
        <div className="bg-white rounded-lg shadow-sm border p-8 text-center text-gray-400">
          <svg className="animate-spin h-5 w-5 mx-auto mb-2" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Scanning datasets...
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title="Data Ingest"
      description="Normalize and merge weekly GeoTIFF files for each dataset."
      actions={
        <button
          onClick={loadStatus}
          className="text-sm px-3 py-1 border rounded hover:bg-gray-50 transition-colors"
        >
          Rescan
        </button>
      }
    >
      {scanError && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm">
          {scanError}
        </div>
      )}

      {Object.keys(datasets).length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm border p-8 text-center">
          <p className="text-gray-400 mb-2">No raw data directories found</p>
          <p className="text-xs text-gray-400">
            Place GeoTIFF files in <code className="bg-gray-100 px-1 rounded">data/raw/</code> and click Rescan.
          </p>
        </div>
      ) : (
        Object.entries(datasets).map(([name, ds]) => {
          const total = ds.canonical + ds.needs_normalize + ds.needs_merge;
          const allDone = ds.needs_normalize === 0 && ds.needs_merge === 0;
          const result = results[name];

          return (
            <div key={name} className="bg-white rounded-lg shadow-sm border">
              <div className="px-6 py-4 border-b flex justify-between items-center">
                <div>
                  <h2 className="text-lg font-semibold">{name}</h2>
                  <p className="text-sm text-gray-500">
                    {ds.total_files} files &middot; {total} week groups
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {allDone ? (
                    <span className="px-3 py-1 bg-green-100 text-green-700 rounded text-sm font-medium">
                      \u2713 All ingested
                    </span>
                  ) : (
                    <button
                      onClick={() => handleIngest(name)}
                      disabled={running[name]}
                      className="px-4 py-2 bg-primary text-white rounded-md text-sm hover:bg-primary-dark disabled:opacity-50 transition-colors"
                    >
                      {running[name] ? (
                        <span className="flex items-center gap-2">
                          <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                          Running...
                        </span>
                      ) : (
                        "Run Ingest"
                      )}
                    </button>
                  )}
                </div>
              </div>

              <div className="px-4 sm:px-6 py-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="text-center p-3 bg-green-50 rounded">
                  <p className="text-2xl font-bold text-green-700">{ds.canonical}</p>
                  <p className="text-xs text-gray-500">Canonical (ready)</p>
                </div>
                <div className="text-center p-3 bg-blue-50 rounded">
                  <p className="text-2xl font-bold text-blue-700">{ds.needs_normalize}</p>
                  <p className="text-xs text-gray-500">Needs normalize</p>
                </div>
                <div className="text-center p-3 bg-yellow-50 rounded">
                  <p className="text-2xl font-bold text-yellow-700">{ds.needs_merge}</p>
                  <p className="text-xs text-gray-500">Needs merge</p>
                </div>
              </div>

              {total > 0 && (
                <div className="px-6 pb-3">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-500 rounded-full transition-all"
                        style={{ width: `${(ds.canonical / total) * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-500">
                      {ds.canonical}/{total}
                    </span>
                  </div>
                </div>
              )}

              {result && (
                <div className="px-6 pb-4">
                  <div
                    className={`rounded p-3 text-xs font-mono max-h-32 overflow-y-auto ${
                      result.failed > 0
                        ? "bg-red-50 text-red-700 border border-red-200"
                        : "bg-black text-green-400"
                    }`}
                  >
                    {result.logs.map((line, i) => (
                      <div key={i}>{line}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })
      )}
    </PageLayout>
  );
}
