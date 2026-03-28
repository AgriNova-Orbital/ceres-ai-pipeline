"use client";

import { useState } from "react";
import PageLayout from "@/components/PageLayout";
import JobPanel from "@/components/JobPanel";

export default function BuildPage() {
  const [action, setAction] = useState("build_level");
  const [level, setLevel] = useState("1");
  const [rawDir, setRawDir] = useState("data/raw/france_2025_weekly");
  const [maxPatches, setMaxPatches] = useState("12000");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    setLoading(true); setResult("");
    try {
      const res = await fetch("/api/run/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, level, raw_dir: rawDir, max_patches: maxPatches }),
      });
      const data = await res.json();
      setResult(res.ok ? `Queued: ${data.job_id}` : `Error: ${data.error}`);
    } catch { setResult("Connection error"); }
    setLoading(false);
  }

  return (
    <PageLayout title="Build Dataset">
      <div className="bg-white rounded-lg shadow-sm border p-6 space-y-6">
        <div>
          <label className="block text-sm font-medium mb-2">Action</label>
          <div className="space-y-2">
            {[{ k: "build_level", l: "Build Level Dataset", d: "Build staged patches for selected level" },
              { k: "dry_run", l: "Dry Run", d: "Preview what would be built" }].map((a) => (
              <label key={a.k} className={`flex items-start gap-3 p-3 rounded border cursor-pointer ${action === a.k ? "border-primary bg-blue-50" : "border-gray-200"}`}>
                <input type="radio" name="action" checked={action === a.k} onChange={() => setAction(a.k)} className="mt-1" />
                <div><p className="font-medium text-sm">{a.l}</p><p className="text-xs text-gray-500">{a.d}</p></div>
              </label>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-sm font-medium text-gray-700">Level</span>
            <select value={level} onChange={(e) => setLevel(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
              <option value="1">Level 1 (64px)</option>
              <option value="2">Level 2 (128px)</option>
              <option value="4">Level 4 (256px)</option>
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-700">Max Patches</span>
            <input value={maxPatches} onChange={(e) => setMaxPatches(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" />
          </label>
          <label className="block col-span-2">
            <span className="text-sm font-medium text-gray-700">Raw Data Directory</span>
            <input value={rawDir} onChange={(e) => setRawDir(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" />
          </label>
        </div>
        <div>
          <button onClick={handleSubmit} disabled={loading} className="px-6 py-2 bg-primary text-white rounded-md hover:bg-primary-dark disabled:opacity-50 text-sm font-medium">
            {loading ? "Submitting..." : "Run Build"}
          </button>
          {result && <p className={`mt-2 text-sm ${result.startsWith("Error") ? "text-red-600" : "text-green-600"}`}>{result}</p>}
        </div>
      </div>
      <JobPanel />
    </PageLayout>
  );
}
