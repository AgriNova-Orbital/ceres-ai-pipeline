"use client";

import { useState } from "react";
import PageLayout from "@/components/PageLayout";
import JobPanel from "@/components/JobPanel";

const actions = [
  { key: "download_all", label: "Download All", desc: "Full download from Earth Engine" },
  { key: "preview_export", label: "Preview Export (dry run)", desc: "Dry run to preview what would be downloaded" },
  { key: "refresh_inventory", label: "Refresh Inventory", desc: "Scan and update data inventory" },
];

export default function DownloaderPage() {
  const [action, setAction] = useState("preview_export");
  const [stage, setStage] = useState("1");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [limit, setLimit] = useState("4");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    setLoading(true);
    setResult("");
    try {
      const res = await fetch("/api/run/downloader", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, stage, start_date: startDate, end_date: endDate, limit }),
      });
      const data = await res.json();
      setResult(res.ok ? `Queued: ${data.job_id}` : `Error: ${data.error}`);
    } catch { setResult("Connection error"); }
    setLoading(false);
  }

  return (
    <PageLayout title="Downloader">
      <div className="bg-white rounded-lg shadow-sm border p-6 space-y-6">
        <div>
          <label className="block text-sm font-medium mb-2">Action</label>
          <div className="space-y-2">
            {actions.map((a) => (
              <label key={a.key} className={`flex items-start gap-3 p-3 rounded border cursor-pointer ${action === a.key ? "border-primary bg-blue-50" : "border-gray-200"}`}>
                <input type="radio" name="action" value={a.key} checked={action === a.key} onChange={() => setAction(a.key)} className="mt-1" />
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
        </div>
        <SubmitBtn loading={loading} onClick={handleSubmit} label="Run Downloader" result={result} />
      </div>
      <JobPanel />
    </PageLayout>
  );
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)}
        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm" />
    </label>
  );
}

function SubmitBtn({ loading, onClick, label, result }: { loading: boolean; onClick: () => void; label: string; result: string }) {
  return (
    <div>
      <button onClick={onClick} disabled={loading}
        className="px-6 py-2 bg-primary text-white rounded-md hover:bg-primary-dark disabled:opacity-50 text-sm font-medium">
        {loading ? "Submitting..." : label}
      </button>
      {result && <p className={`mt-2 text-sm ${result.startsWith("Error") ? "text-red-600" : "text-green-600"}`}>{result}</p>}
    </div>
  );
}
