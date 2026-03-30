"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";

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
  const [results, setResults] = useState<Record<string, { merged: number; normalized: number; failed: number; logs: string[] }>>({});
  const [running, setRunning] = useState<Record<string, boolean>>({});

  async function loadStatus() {
    try {
      const res = await fetch("/api/ingest/status");
      const data = await res.json();
      setDatasets(data.datasets || {});
    } catch { /* */ }
    setLoading(false);
  }

  useEffect(() => { loadStatus(); }, []);

  async function handleIngest(name: string) {
    setRunning((p) => ({ ...p, [name]: true }));
    try {
      const res = await fetch("/api/run/downloader", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "refresh_inventory", raw_dir: `data/raw/${name}` }),
      });
      const data = await res.json();
      if (res.ok) {
        setResults((p) => ({
          ...p,
          [name]: { merged: 0, normalized: 0, failed: 0, logs: [`Job queued: ${data.job_id}`] },
        }));
      }
    } catch {
      setResults((p) => ({
        ...p,
        [name]: { merged: 0, normalized: 0, failed: 1, logs: ["Submit failed"] },
      }));
    }
    setRunning((p) => ({ ...p, [name]: false }));
  }

  if (loading) return <div className="p-8 text-center text-gray-400">Loading...</div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-4 sm:px-8 py-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-primary hover:underline">&larr; Home</Link>
          <h1 className="text-xl font-bold">Data Ingest</h1>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={loadStatus} className="text-sm px-3 py-1 border rounded hover:bg-gray-50">Rescan</button>
          <LogoutButton />
        </div>
      </header>

      <main className="max-w-5xl mx-auto p-6 space-y-6">
        {Object.keys(datasets).length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border p-8 text-center text-gray-400">
            No raw data directories found in data/raw/
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
                    <p className="text-sm text-gray-500">{ds.total_files} files · {total} week groups</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {allDone ? (
                      <span className="px-3 py-1 bg-green-100 text-green-700 rounded text-sm font-medium">All ingested</span>
                    ) : (
                      <button onClick={() => handleIngest(name)} disabled={running[name]}
                        className="px-4 py-2 bg-primary text-white rounded-md text-sm hover:bg-primary-dark disabled:opacity-50">
                        {running[name] ? "Running..." : "Run Ingest"}
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

                {/* Progress bar */}
                {total > 0 && (
                  <div className="px-6 pb-2">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div className="h-full bg-green-500 rounded-full"
                          style={{ width: `${(ds.canonical / total) * 100}%` }} />
                      </div>
                      <span className="text-xs text-gray-500">{ds.canonical}/{total}</span>
                    </div>
                  </div>
                )}

                {/* Result logs */}
                {result && (
                  <div className="px-6 pb-4">
                    <div className="bg-black text-green-400 rounded p-3 text-xs font-mono max-h-32 overflow-y-auto">
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
      </main>
    </div>
  );
}
