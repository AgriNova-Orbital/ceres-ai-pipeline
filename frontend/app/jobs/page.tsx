"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";

interface Job {
  id: string;
  section: string;
  action: string;
  status: string;
  enqueued_at: string;
  started_at?: string;
  ended_at?: string;
  error?: string;
  source?: string;
}

interface Worker {
  name: string;
  state: string;
  current_job: string | null;
}

const statusColors: Record<string, string> = {
  enqueued: "bg-yellow-100 text-yellow-800",
  queued: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  finished: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  unknown: "bg-gray-100 text-gray-800",
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const res = await fetch("/api/jobs");
      const data = await res.json();
      setJobs(data.jobs || []);
      setWorkers(data.workers || []);
    } catch { /* ignore */ }
    setLoading(false);
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, []);

  const filtered = filter === "all" ? jobs : jobs.filter((j) => j.status === filter);
  const counts = {
    all: jobs.length,
    queued: jobs.filter((j) => j.status === "queued" || j.status === "enqueued").length,
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
          <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">Auto-refresh 3s</span>
        </div>
        <div className="flex items-center gap-3">
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
                  <span className={`w-2 h-2 rounded-full ${w.state === "busy" ? "bg-yellow-500" : "bg-green-500"}`} />
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

        {/* Jobs Table */}
        <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
          {loading ? (
            <p className="p-8 text-center text-gray-400">Loading...</p>
          ) : filtered.length === 0 ? (
            <p className="p-8 text-center text-gray-400">No jobs found</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr className="text-left text-gray-500">
                  <th className="px-4 py-3">Job ID</th>
                  <th className="px-4 py-3">Section</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Enqueued</th>
                  <th className="px-4 py-3">Ended</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filtered.map((j) => (
                  <tr key={j.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs">{j.id.slice(0, 12)}...</td>
                    <td className="px-4 py-3 font-medium">{j.section}</td>
                    <td className="px-4 py-3 text-gray-500">{j.action}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[j.status] || statusColors.unknown}`}>
                        {j.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{formatTime(j.enqueued_at)}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {j.ended_at ? formatTime(j.ended_at) : j.started_at ? formatTime(j.started_at) : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </div>
  );
}

function formatTime(iso: string): string {
  if (!iso) return "-";
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-TW", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return iso;
  }
}
