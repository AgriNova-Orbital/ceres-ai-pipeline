"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";

interface Job {
  id: string;
  section: string;
  action: string;
  status: string;
  description?: string;
  enqueued_at: string;
  started_at?: string;
  ended_at?: string;
  meta?: Record<string, unknown>;
  result?: Record<string, string> | string;
  error?: string;
}

interface Worker {
  name: string;
  state: string;
  current_job: string | null;
}

const statusColors: Record<string, string> = {
  queued: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  finished: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [filter, setFilter] = useState("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState("500");
  const [totalJobs, setTotalJobs] = useState(0);

  async function load() {
    try {
      const query = limit === "all" ? "/api/jobs?all=1" : `/api/jobs?limit=${limit}`;
      const res = await fetch(query);
      const data = await res.json();
      setJobs(data.jobs || []);
      setWorkers(data.workers || []);
      setTotalJobs(Number(data.total || 0));
    } catch { /* ignore */ }
    setLoading(false);
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, [limit]);

  const filtered = filter === "all" ? jobs : jobs.filter((j) => j.status === filter);
  const counts = {
    all: jobs.length,
    queued: jobs.filter((j) => j.status === "queued").length,
    running: jobs.filter((j) => j.status === "running").length,
    finished: jobs.filter((j) => j.status === "finished").length,
    failed: jobs.filter((j) => j.status === "failed").length,
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-8 py-4 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-primary hover:underline">&larr; Home</Link>
          <h1 className="text-xl font-bold">Jobs Monitor</h1>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            className="text-sm px-2 py-1 border rounded bg-white"
          >
            <option value="100">100</option>
            <option value="500">500</option>
            <option value="1000">1000</option>
            <option value="all">All</option>
          </select>
          <span className="text-xs text-gray-400">showing {jobs.length}/{totalJobs || jobs.length}</span>
          <button onClick={load} className="text-sm px-3 py-1 border rounded hover:bg-gray-50">Refresh</button>
          <LogoutButton />
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Workers */}
        <section className="bg-white rounded-lg shadow-sm border p-4">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Workers</h2>
          {workers.length === 0 ? (
            <p className="text-gray-400 text-sm">No workers connected</p>
          ) : (
            <div className="flex gap-3 flex-wrap">
              {workers.map((w) => (
                <div key={w.name} className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded border">
                  <span className={`w-2 h-2 rounded-full ${w.state === "busy" ? "bg-yellow-500 animate-pulse" : "bg-green-500"}`} />
                  <span className="font-mono text-xs">{w.name}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${w.state === "busy" ? "bg-yellow-100 text-yellow-700" : "text-gray-400"}`}>
                    {w.state}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Filter Tabs */}
        <div className="flex gap-2">
          {[
            { key: "all", label: `All (${counts.all})` },
            { key: "queued", label: `Queued (${counts.queued})` },
            { key: "running", label: `Running (${counts.running})` },
            { key: "finished", label: `Finished (${counts.finished})` },
            { key: "failed", label: `Failed (${counts.failed})` },
          ].map((t) => (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              className={`px-3 py-1.5 text-sm rounded-md border ${filter === t.key ? "bg-primary text-white border-primary" : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Jobs */}
        <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
          {loading ? (
            <p className="p-8 text-center text-gray-400">Loading...</p>
          ) : filtered.length === 0 ? (
            <p className="p-8 text-center text-gray-400">No jobs found</p>
          ) : (
            <div className="divide-y">
              {filtered.map((j) => (
                <div key={j.id} className="hover:bg-gray-50">
                  <button
                    onClick={() => setExpanded(expanded === j.id ? null : j.id)}
                    className="w-full px-4 py-3 flex items-center gap-4 text-left text-sm"
                  >
                    <span className="font-mono text-xs text-gray-400 w-20">{j.id.slice(0, 8)}</span>
                    <span className="font-medium w-24">{j.section}</span>
                    <span className="text-gray-500 w-32 truncate">{j.action}</span>
                    <StatusBadge status={j.status} />
                    {j.status === "running" && j.meta?.progress != null && (
                      <ProgressBar pct={Number(j.meta.progress)} step={String(j.meta.step ?? "")} />
                    )}
                    {j.status === "queued" && (
                      <span className="text-xs text-gray-400 italic">waiting for worker</span>
                    )}
                    <span className="text-gray-400 text-xs ml-auto">{formatTime(j.enqueued_at)}</span>
                    <span className="text-gray-300">{expanded === j.id ? "▲" : "▼"}</span>
                  </button>

                  {expanded === j.id && (
                    <div className="px-4 pb-4 pl-32 space-y-2 text-sm">
                      {String(j.meta?.step ?? "") && (
                        <InfoRow label="Current Step" value={String(j.meta?.step ?? "")} />
                      )}
                      {j.meta?.progress != null && Number(j.meta?.progress) > 0 && (
                        <InfoRow label="Progress" value={`${Number(j.meta?.progress)}%`} />
                      )}
                      {j.started_at && (
                        <InfoRow label="Started" value={formatTime(j.started_at)} />
                      )}
                      {j.ended_at && (
                        <InfoRow label="Ended" value={formatTime(j.ended_at)} />
                      )}
                      {j.result && (
                        <div>
                          <p className="text-gray-500 text-xs font-medium mb-1">Result:</p>
                          <pre className="bg-gray-50 p-2 rounded text-xs overflow-x-auto max-h-32">
                            {typeof j.result === "string" ? j.result : JSON.stringify(j.result, null, 2)}
                          </pre>
                        </div>
                      )}
                      {j.error && (
                        <div>
                          <p className="text-red-600 text-xs font-medium mb-1">Error:</p>
                          <pre className="bg-red-50 p-2 rounded text-xs text-red-700 overflow-x-auto max-h-40 whitespace-pre-wrap">
                            {j.error}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    queued: "bg-yellow-100 text-yellow-800",
    running: "bg-blue-100 text-blue-800 animate-pulse",
    finished: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${colors[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

function ProgressBar({ pct, step }: { pct: number; step?: string }) {
  return (
    <div className="flex items-center gap-2 flex-1 max-w-xs">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-500"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs text-gray-500 whitespace-nowrap">{pct}%</span>
      {step && <span className="text-xs text-gray-400 truncate max-w-24">{step}</span>}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-gray-500 text-xs w-20">{label}:</span>
      <span className="text-gray-800 text-xs">{value}</span>
    </div>
  );
}

function formatTime(iso: string): string {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("zh-TW", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return iso;
  }
}
