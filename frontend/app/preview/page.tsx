"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import PageLayout from "@/components/PageLayout";
import JobPanel from "@/components/JobPanel";

export default function PreviewPage() {
  return (
    <Suspense fallback={<PreviewShell />}>
      <PreviewContent />
    </Suspense>
  );
}

function PreviewShell() {
  return (
    <PageLayout title="Preview" description="Preview raster and patch data as images.">
      <div className="bg-white rounded-lg shadow-sm border p-6 text-sm text-gray-500">Loading preview controls...</div>
      <JobPanel />
    </PageLayout>
  );
}

function PreviewContent() {
  const searchParams = useSearchParams();
  const initialType = searchParams.get("type") === "patch" ? "patch" : "raw";
  const [type, setType] = useState<"raw" | "patch">(initialType);
  const [path, setPath] = useState(searchParams.get("path") || "");
  const [bands, setBands] = useState("1,2,3");
  const [timeIdx, setTimeIdx] = useState("0");
  const [imgUrl, setImgUrl] = useState("");
  const [imgLoading, setImgLoading] = useState(false);
  const [error, setError] = useState("");

  function handlePreview() {
    setError("");
    setImgUrl("");
    if (!path) {
      setError("File path is required");
      return;
    }
    setImgLoading(true);
    const params = new URLSearchParams({ path, max_size: "512" });
    if (type === "raw") params.set("bands", bands);
    else params.set("t", timeIdx);
    setImgUrl(`/api/preview/${type}?${params.toString()}`);
  }

  return (
    <PageLayout
      title="Preview"
      description="Preview raster and patch data as images."
    >
      <div className="bg-white rounded-lg shadow-sm border p-6 space-y-6">
        <div className="flex gap-4">
          <label
            className={`flex items-center gap-2 px-4 py-2 rounded border cursor-pointer transition-colors ${
              type === "raw" ? "border-primary bg-blue-50" : "border-gray-200 hover:border-gray-300"
            }`}
          >
            <input
              type="radio"
              checked={type === "raw"}
              onChange={() => setType("raw")}
            />
            Raw Raster
          </label>
          <label
            className={`flex items-center gap-2 px-4 py-2 rounded border cursor-pointer transition-colors ${
              type === "patch" ? "border-primary bg-blue-50" : "border-gray-200 hover:border-gray-300"
            }`}
          >
            <input
              type="radio"
              checked={type === "patch"}
              onChange={() => setType("patch")}
            />
            Patch
          </label>
        </div>

        <label className="block">
          <span className="text-sm font-medium">File Path</span>
          <input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="data/raw/france_2025_weekly/..."
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
          />
        </label>

        {type === "raw" ? (
          <label className="block">
            <span className="text-sm font-medium">Bands</span>
            <input
              value={bands}
              onChange={(e) => setBands(e.target.value)}
              placeholder="1,2,3"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
            />
          </label>
        ) : (
          <label className="block">
            <span className="text-sm font-medium">Time Index</span>
            <input
              type="number"
              value={timeIdx}
              onChange={(e) => setTimeIdx(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary focus:border-primary"
            />
          </label>
        )}

        <div>
          <button
            onClick={handlePreview}
            className="px-6 py-2 bg-primary text-white rounded-md hover:bg-primary-dark text-sm font-medium transition-colors"
          >
            Preview
          </button>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </div>

        {imgUrl && (
          <div className="border rounded-lg p-4 bg-gray-50 relative min-h-[100px]">
            {imgLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-50 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Loading preview...
                </div>
              </div>
            )}
            <img
              src={imgUrl}
              alt="Preview"
              className="max-w-full"
              onLoad={() => setImgLoading(false)}
              onError={() => {
                setImgLoading(false);
                setError("Failed to load preview image. Check the file path.");
              }}
            />
          </div>
        )}
      </div>
      <JobPanel />
    </PageLayout>
  );
}
