"use client";

import { useState } from "react";
import PageLayout from "@/components/PageLayout";
import JobPanel from "@/components/JobPanel";

export default function TrainingPage() {
  const [action, setAction] = useState("dry_run");
  const [levels, setLevels] = useState("1,2,4");
  const [steps, setSteps] = useState("100,500,2000");
  const [epochs, setEpochs] = useState("10");
  const [batchSize, setBatchSize] = useState("8");
  const [device, setDevice] = useState("cpu");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    setLoading(true); setResult("");
    const body: Record<string, unknown> = { action };
    if (action === "run_matrix") { body.levels = levels; body.steps = steps; body.dry_run = true; }
    if (action === "train") { body.epochs = Number(epochs); body.batch_size = Number(batchSize); body.device = device; }
    try {
      const res = await fetch("/api/run/train", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await res.json();
      setResult(res.ok ? `Queued: ${data.job_id}` : `Error: ${data.error}`);
    } catch { setResult("Connection error"); }
    setLoading(false);
  }

  return (
    <PageLayout title="Training">
      <div className="bg-white rounded-lg shadow-sm border p-6 space-y-6">
        <div>
          <label className="block text-sm font-medium mb-2">Action</label>
          <div className="space-y-2">
            {[{ k: "dry_run", l: "Dry Run", d: "Preview training matrix" },
              { k: "run_matrix", l: "Run Matrix", d: "Run training matrix across levels and steps" },
              { k: "train", l: "Single Train", d: "Train a single model with specific params" }].map((a) => (
              <label key={a.k} className={`flex items-start gap-3 p-3 rounded border cursor-pointer ${action === a.k ? "border-primary bg-blue-50" : "border-gray-200"}`}>
                <input type="radio" name="action" checked={action === a.k} onChange={() => setAction(a.k)} className="mt-1" />
                <div><p className="font-medium text-sm">{a.l}</p><p className="text-xs text-gray-500">{a.d}</p></div>
              </label>
            ))}
          </div>
        </div>
        {action === "run_matrix" && (
          <div className="grid grid-cols-2 gap-4">
            <label className="block"><span className="text-sm font-medium">Levels</span><input value={levels} onChange={(e) => setLevels(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" placeholder="1,2,4" /></label>
            <label className="block"><span className="text-sm font-medium">Steps</span><input value={steps} onChange={(e) => setSteps(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" placeholder="100,500,2000" /></label>
          </div>
        )}
        {action === "train" && (
          <div className="grid grid-cols-2 gap-4">
            <label className="block"><span className="text-sm font-medium">Epochs</span><input type="number" value={epochs} onChange={(e) => setEpochs(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" /></label>
            <label className="block"><span className="text-sm font-medium">Batch Size</span><input type="number" value={batchSize} onChange={(e) => setBatchSize(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" /></label>
            <label className="block"><span className="text-sm font-medium">Device</span>
              <select value={device} onChange={(e) => setDevice(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
                <option value="cpu">CPU</option>
                <option value="cuda">CUDA (GPU)</option>
              </select>
            </label>
          </div>
        )}
        <div>
          <button onClick={handleSubmit} disabled={loading} className="px-6 py-2 bg-primary text-white rounded-md hover:bg-primary-dark disabled:opacity-50 text-sm font-medium">
            {loading ? "Submitting..." : "Run Training"}
          </button>
          {result && <p className={`mt-2 text-sm ${result.startsWith("Error") ? "text-red-600" : "text-green-600"}`}>{result}</p>}
        </div>
      </div>
      <JobPanel />
    </PageLayout>
  );
}
