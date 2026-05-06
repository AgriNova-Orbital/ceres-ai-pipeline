"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";
import FeedbackMessage from "@/components/FeedbackMessage";
import SubmitButton from "@/components/SubmitButton";
import { readApiResponse } from "@/lib/api-response";

interface MatrixCell {
  level: number;
  steps: number;
  status: string;
  jobId?: string;
  error?: string;
  outputDir?: string;
}

interface JobInfo {
  id: string;
  description: string;
  status: string;
  meta: Record<string, unknown>;
  result: Record<string, string>;
  error?: string;
}

export default function TrainingPage() {
  const [action, setAction] = useState("dry_run");
  const [levels, setLevels] = useState("1,2,4");
  const [steps, setSteps] = useState("100,500,2000");
  const [device, setDevice] = useState("cpu");
  const [epochs, setEpochs] = useState("10");
  const [batchSize, setBatchSize] = useState("8");
  const [lr, setLr] = useState("0.001");
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [matrixCells, setMatrixCells] = useState<MatrixCell[]>([]);
  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const jobsInFlightRef = useRef(false);


  const hasActiveMatrixJobs = useMemo(
    () => matrixCells.some((c) => c.status === "queued" || c.status === "running"),
    [matrixCells]
  );

  function buildMatrix() {
    const lvls = levels.split(",").map((s) => parseInt(s.trim())).filter(Boolean);
    const stps = steps.split(",").map((s) => parseInt(s.trim())).filter(Boolean);
    const cells: MatrixCell[] = [];
    for (const lv of lvls) {
      for (const st of stps) {
        const existing = matrixCells.find((c) => c.level === lv && c.steps === st);
        cells.push(existing || { level: lv, steps: st, status: "pending" });
      }
    }
    setMatrixCells(cells);
  }

  useEffect(() => { buildMatrix(); }, [levels, steps]);

  useEffect(() => {
    async function loadJobs() {
      if (jobsInFlightRef.current) return;
      jobsInFlightRef.current = true;
      try {
        const res = await fetch("/api/jobs", { cache: "no-store" });
        const response = await readApiResponse(res, "Failed to load jobs");
        if (!response.ok) {
          setError(response.error);
          return;
        }
        setJobs((response.data.jobs as JobInfo[] | undefined) || []);
      } catch {
        setError("Connection error");
      } finally {
        jobsInFlightRef.current = false;
      }
    }

    const tick = () => {
      if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
      if (!hasActiveMatrixJobs) return;
      loadJobs();
    };

    loadJobs();
    const id = setInterval(tick, 12000);
    return () => clearInterval(id);
  }, [hasActiveMatrixJobs]);

  useEffect(() => {
    setMatrixCells((prev) =>
      prev.map((cell) => {
        const cellDesc = `level=${cell.level} steps=${cell.steps}`;
        const matchJob = jobs.find(
          (j) => j.description?.includes(cellDesc) || j.description?.includes(`train`)
        );
        if (matchJob) {
          return {
            ...cell,
            status:
              matchJob.status === "finished" ? "done" :
              matchJob.status === "failed" ? "failed" :
              matchJob.status === "running" ? "running" : cell.status,
            jobId: matchJob.id,
            error: matchJob.error,
          };
        }
        return cell;
      })
    );
  }, [jobs]);

  async function handleSubmit() {
    setLoading(true);
    setResult("");
    setError("");
    try {
      const res = await fetch("/api/run/train", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          levels,
          steps,
          device,
          epochs: Number(epochs),
          batch_size: Number(batchSize),
          lr: Number(lr),
        }),
      });
      const response = await readApiResponse(res, "Failed to submit training job");
      const jobId = response.ok && typeof response.data.job_id === "string" ? response.data.job_id : null;
      if (jobId) {
        setResult(`Job queued: ${jobId}`);
        setMatrixCells((prev) => prev.map((c) => ({ ...c, status: "queued", jobId })));
      } else {
        setError(response.ok ? "Training job did not return a job id" : response.error);
      }
    } catch {
      setError("Connection error. Please check if the server is running.");
    }
    setLoading(false);
  }

  async function handleRetry(cell: MatrixCell) {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/run/train", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "run_matrix",
          levels: String(cell.level),
          steps: String(cell.steps),
          dry_run: false,
        }),
      });
      const response = await readApiResponse(res, "Failed to retry");
      const jobId = response.ok && typeof response.data.job_id === "string" ? response.data.job_id : null;
      if (jobId) {
        setMatrixCells((prev) =>
          prev.map((c) =>
            c.level === cell.level && c.steps === cell.steps
              ? { ...c, status: "queued", jobId, error: undefined }
              : c
          )
        );
        setResult(`Retry queued: ${jobId}`);
      } else {
        setError(response.ok ? "Training job did not return a job id" : response.error);
      }
    } catch {
      setError("Connection error");
    }
    setLoading(false);
  }

  const doneCount = matrixCells.filter((c) => c.status === "done").length;
  const failCount = matrixCells.filter((c) => c.status === "failed").length;
  const runCount = matrixCells.filter((c) => c.status === "running").length;
  const totalCount = matrixCells.length;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-4 sm:px-8 py-4">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-primary hover:underline text-sm">&larr; Home</Link>
            <h1 className="text-xl font-bold">Training Matrix</h1>
          </div>
          <LogoutButton />
        </div>
      </header>

      <main className="max-w-6xl mx-auto p-6 space-y-6">
        {/* Feedback */}
        {(result || error) && (
          <FeedbackMessage
            message={result || error}
            type={result ? "success" : "error"}
            onClear={() => { setResult(""); setError(""); }}
          />
        )}

        {/* Input Form */}
        <div className="bg-white rounded-lg shadow-sm border p-6 space-y-4">
          <h2 className="text-lg font-semibold">Configuration</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Action</span>
              <select
                value={action}
                onChange={(e) => setAction(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
              >
                <option value="dry_run">Dry Run (preview)</option>
                <option value="run_matrix">Run Matrix</option>
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Levels</span>
              <input
                value={levels}
                onChange={(e) => setLevels(e.target.value)}
                placeholder="1,2,4"
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Steps</span>
              <input
                value={steps}
                onChange={(e) => setSteps(e.target.value)}
                placeholder="100,500,2000"
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Device</span>
              <select
                value={device}
                onChange={(e) => setDevice(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
              >
                <option value="cpu">CPU</option>
                <option value="cuda">CUDA (GPU)</option>
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Epochs</span>
              <input
                type="number"
                value={epochs}
                onChange={(e) => setEpochs(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Batch Size</span>
              <input
                type="number"
                value={batchSize}
                onChange={(e) => setBatchSize(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Learning Rate</span>
              <input
                type="number"
                step="0.0001"
                value={lr}
                onChange={(e) => setLr(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
              />
            </label>
          </div>
          <div className="flex items-center gap-4">
            <SubmitButton
              loading={loading}
              onClick={handleSubmit}
              label={action === "dry_run" ? "Dry Run" : "Run Matrix"}
              loadingLabel="Submitting\u2026"
            />
          </div>
        </div>

        {/* Status Summary */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg shadow-sm border p-4">
            <p className="text-sm text-gray-500">Total Cells</p>
            <p className="text-2xl font-bold">{totalCount}</p>
          </div>
          <div className="bg-white rounded-lg shadow-sm border p-4">
            <p className="text-sm text-gray-500">Running</p>
            <p className="text-2xl font-bold text-blue-600">{runCount}</p>
          </div>
          <div className="bg-white rounded-lg shadow-sm border p-4">
            <p className="text-sm text-gray-500">Completed</p>
            <p className="text-2xl font-bold text-green-600">{doneCount}</p>
          </div>
          <div className="bg-white rounded-lg shadow-sm border p-4">
            <p className="text-sm text-gray-500">Failed</p>
            <p className="text-2xl font-bold text-red-600">{failCount}</p>
          </div>
        </div>

        {/* Matrix Table */}
        <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
          <div className="px-4 py-3 bg-gray-50 border-b flex justify-between items-center">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Matrix Status</h2>
            <div className="flex gap-2">
              <a
                href="/runs/staged_final/summary.csv"
                target="_blank"
                className="text-xs text-primary hover:underline px-2 py-1 border rounded"
              >
                summary.csv
              </a>
              <a
                href="/runs/staged_final/eval_metrics.csv"
                target="_blank"
                className="text-xs text-primary hover:underline px-2 py-1 border rounded"
              >
                eval_metrics.csv
              </a>
            </div>
          </div>

          {matrixCells.length === 0 ? (
            <div className="p-8 text-center">
              <p className="text-gray-400 mb-2">No matrix cells configured</p>
              <p className="text-xs text-gray-400">
                Enter levels and steps above to configure the training matrix
              </p>
            </div>
          ) : (
            <table className="w-full text-sm min-w-[700px]">
              <thead className="bg-gray-50 border-b">
                <tr className="text-left text-gray-500">
                  <th className="px-4 py-2">Level</th>
                  <th className="px-4 py-2">Steps</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Progress</th>
                  <th className="px-4 py-2">Output</th>
                  <th className="px-4 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {matrixCells.map((cell) => {
                  const job = jobs.find((j) => j.id === cell.jobId);
                  const progress = Number(job?.meta?.progress ?? (cell.status === "done" ? 100 : 0));
                  const step = String(job?.meta?.step ?? cell.status);
                  return (
                    <tr key={`${cell.level}-${cell.steps}`} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium">L{cell.level}</td>
                      <td className="px-4 py-2">{cell.steps}</td>
                      <td className="px-4 py-2">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            cell.status === "done" ? "bg-green-100 text-green-800" :
                            cell.status === "running" ? "bg-blue-100 text-blue-800 animate-pulse" :
                            cell.status === "failed" ? "bg-red-100 text-red-800" :
                            cell.status === "queued" ? "bg-yellow-100 text-yellow-800" :
                            "bg-gray-100 text-gray-500"
                          }`}
                        >
                          {cell.status}
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden w-24">
                            <div
                              className={`h-full rounded-full transition-all ${
                                cell.status === "done" ? "bg-green-500" :
                                cell.status === "failed" ? "bg-red-500" :
                                "bg-blue-500"
                              }`}
                              style={{ width: `${progress}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-500 w-10">{progress}%</span>
                        </div>
                        <span className="text-xs text-gray-400">{step}</span>
                      </td>
                      <td className="px-4 py-2 text-xs font-mono text-gray-400">
                        runs/L{cell.level}_s{cell.steps}
                      </td>
                      <td className="px-4 py-2">
                        {cell.status === "failed" && (
                          <button
                            onClick={() => handleRetry(cell)}
                            disabled={loading}
                            className="text-xs text-red-600 hover:underline mr-2 disabled:opacity-50"
                          >
                            Retry
                          </button>
                        )}
                        {cell.error && (
                          <span className="text-xs text-red-500 truncate max-w-32 block">
                            {cell.error}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </div>
  );
}
