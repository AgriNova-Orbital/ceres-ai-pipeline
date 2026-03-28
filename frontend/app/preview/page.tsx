"use client";

import { useState } from "react";
import PageLayout from "@/components/PageLayout";
import JobPanel from "@/components/JobPanel";

export default function PreviewPage() {
  const [type, setType] = useState<"raw" | "patch">("raw");
  const [path, setPath] = useState("");
  const [bands, setBands] = useState("1,2,3");
  const [timeIdx, setTimeIdx] = useState("0");
  const [imgUrl, setImgUrl] = useState("");
  const [error, setError] = useState("");

  function handlePreview() {
    setError(""); setImgUrl("");
    if (!path) { setError("Path is required"); return; }
    const params = new URLSearchParams({ path, max_size: "512" });
    if (type === "raw") params.set("bands", bands);
    else params.set("t", timeIdx);
    setImgUrl(`/api/preview/${type}?${params.toString()}`);
  }

  return (
    <PageLayout title="Preview">
      <div className="bg-white rounded-lg shadow-sm border p-6 space-y-6">
        <div className="flex gap-4">
          <label className={`flex items-center gap-2 px-4 py-2 rounded border cursor-pointer ${type === "raw" ? "border-primary bg-blue-50" : "border-gray-200"}`}>
            <input type="radio" checked={type === "raw"} onChange={() => setType("raw")} /> Raw Raster
          </label>
          <label className={`flex items-center gap-2 px-4 py-2 rounded border cursor-pointer ${type === "patch" ? "border-primary bg-blue-50" : "border-gray-200"}`}>
            <input type="radio" checked={type === "patch"} onChange={() => setType("patch")} /> Patch
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium">File Path</span>
          <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="data/raw/france_2025_weekly/..." className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" />
        </label>
        {type === "raw" ? (
          <label className="block"><span className="text-sm font-medium">Bands</span><input value={bands} onChange={(e) => setBands(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" /></label>
        ) : (
          <label className="block"><span className="text-sm font-medium">Time Index</span><input type="number" value={timeIdx} onChange={(e) => setTimeIdx(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" /></label>
        )}
        <div>
          <button onClick={handlePreview} className="px-6 py-2 bg-primary text-white rounded-md hover:bg-primary-dark text-sm font-medium">Preview</button>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </div>
        {imgUrl && (
          <div className="border rounded-lg p-4 bg-gray-50">
            <img src={imgUrl} alt="Preview" className="max-w-full" onError={() => setError("Failed to load preview image")} />
          </div>
        )}
      </div>
      <JobPanel />
    </PageLayout>
  );
}
