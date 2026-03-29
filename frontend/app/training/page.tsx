"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";

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
  const [loading, setLoading] = useState(false);
  const [matrixCells, setMatrixCells] = useState<MatrixCell[]>([]);
  const [jobs, setJobs] = useState<JobInfo[]>([]);

  // Build matrix cells from levels × steps
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

  // Poll jobs
  useEffect(() => {
    async function loadJobs() {
      try {
        const res = await fetch("/api/jobs");
        const data = await res.json();
        setJobs(data.jobs || []);
      } catch { /* */ }
    }
    loadJobs();
    const id = setInterval(loadJobs, 2000);
    return () => clearInterval(id);
  }, []);

  // Update matrix cells from jobs
  useEffect(() => {
    setMatrixCells((prev) =>
      prev.map((cell) => {
        const cellDesc = `level=${cell.level} steps=${cell.steps}`;
        const matchJob = jobs.find(
          (j) => j.description?.includes(cellDesc) || j.description?.includes(`train`)
        );
        if (matchJob) {
          const prog = Number(matchJob.meta?.progress ?? 0);
          const step = String(matchJob.meta?.step ?? matchJob.status);
          return {
            ...cell,
            status: matchJob.status === "finished" ? "done" :
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
      const data = await res.json();
      setResult(res.ok ? `Queued: ${data.job_id}` : `Error: ${data.error}`);
      if (res.ok) {
        // Mark all cells as queued
        setMatrixCells((prev) => prev.map((c) => ({ ...c, status: "queued", jobId: data.job_id })));
      }
    } catch { setResult("Connection error"); }
    setLoading(false);
  }

  async function handleRetry(cell: MatrixCell) {
    setLoading(true);
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
      const data = await res.json();
      if (res.ok) {
        setMatrixCells((prev) =>
          prev.map((c) => c.level === cell.level && c.steps === cell.steps
            ? { ...c, status: "queued", jobId: data.job_id, error: undefined }
            : c)
        );
      }
    } catch { /* */ }
    setLoading(false);
  }

  const lvls = levels.split(",").map((s) => parseInt(s.trim())).filter(Boolean);
  const stps = steps.split(",").map((s) => parseInt(s.trim())).filter(Boolean);
  const doneCount = matrixCells.filter((c) => c.status === "done").length;
  const failCount = matrixCells.filter((c) => c.status === "failed").length;
  const runCount = matrixCells.filter((c) => c.status === "running").length;
  const totalCount = matrixCells.length;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-8 py-4 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-primary hover:underline">&larr; Home</Link>
          <h1 className="text-xl font-bold">Training Matrix</h1>
        </div>
        <LogoutButton />
      </header>

      <main className="max-w-6xl mx-auto p-6 space-y-6">
        {/* Input Form */}
        <div className="bg-white rounded-lg shadow-sm border p-6 space-y-4">
          <h2 className="text-lg font-semibold">Configuration</h2>
          <div className="grid grid-cols-3 gap-4">
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Action</span>
              <select value={action} onChange={(e) => setAction(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
                <option value="dry_run">Dry Run (preview)</option>
                <option value="run_matrix">Run Matrix</option>
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Levels</span>
              <input value={levels} onChange={(e) => setLevels(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" placeholder="1,2,4" />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Steps</span>
              <input value={steps} onChange={(e) => setSteps(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" placeholder="100,500,2000" />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Device</span>
              <select value={device} onChange={(e) => setDevice(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
                <option value="cpu">CPU</option>
                <option value="cuda">CUDA (GPU)</option>
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Epochs</span>
              <input type="number" value={epochs} onChange={(e) => setEpochs(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Batch Size</span>
              <input type="number" value={batchSize} onChange={(e) => setBatchSize(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Learning Rate</span>
              <input type="number" step="0.0001" value={lr} onChange={(e) => setLr(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" />
            </label>
          </div>
          <div className="flex items-center gap-4">
            <button onClick={handleSubmit} disabled={loading}
              className="px-6 py-2 bg-primary text-white rounded-md hover:bg-primary-dark disabled:opacity-50 text-sm font-medium">
              {loading ? "Submitting..." : action === "dry_run" ? "Dry Run" : "Run Matrix"}
            </button>
            {result && (
              <span className={`text-sm ${result.startsWith("Error") ? "text-red-600" : "text-green-600"}`}>{result}</span>
            )}
          </div>
        </div>

        {/* Status Summary */}
        <div className="grid grid-cols-4 gap-4">
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
        <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b flex justify-between items-center">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Matrix Status</h2>
            <div className="flex gap-2">
              <a href="/runs/staged_final/summary.csv" target="_blank"
                className="text-xs text-primary hover:underline px-2 py-1 border rounded">
                summary.csv
              </a>
              <a href="/runs/staged_final/eval_metrics.csv" target="_blank"
                className="text-xs text-primary hover:underline px-2 py-1 border rounded">
                eval_metrics.csv
              </a>
            </div>
          </div>

          {matrixCells.length === 0 ? (
            <p className="p-8 text-center text-gray-400">Configure levels and steps above</p>
          ) : (
            <table className="w-full text-sm">
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
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                          cell.status === "done" ? "bg-green-100 text-green-800" :
                          cell.status === "running" ? "bg-blue-100 text-blue-800 animate-pulse" :
                          cell.status === "failed" ? "bg-red-100 text-red-800" :
                          cell.status === "queued" ? "bg-yellow-100 text-yellow-800" :
                          "bg-gray-100 text-gray-500"
                        }`}>
                          {cell.status}
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden w-24">
                            <div className={`h-full rounded-full transition-all ${
                              cell.status === "done" ? "bg-green-500" :
                              cell.status === "failed" ? "bg-red-500" :
                              "bg-blue-500"
                            }`} style={{ width: `${progress}%` }} />
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
                          <button onClick={() => handleRetry(cell)}
                            className="text-xs text-red-600 hover:underline mr-2">Retry</button>
                        )}
                        {cell.error && (
                          <span className="text-xs text-red-500 truncate max-w-32 block">{cell.error}</span>
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
