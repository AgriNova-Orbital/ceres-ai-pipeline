"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import StatusBadge from "@/components/StatusBadge";
import { readApiResponse } from "@/lib/api-response";

interface JobRecord {
  id: string;
  section: string;
  action: string;
  status: string;
  enqueued_at: string;
}

export default function JobPanel() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const inFlightRef = useRef(false);

  async function loadJobs() {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    try {
      const res = await fetch("/api/jobs", { cache: "no-store" });
      const response = await readApiResponse(res, "Failed to load jobs");
      if (!response.ok) {
        setError(response.error);
        return;
      }
      setError("");
      setJobs((response.data.history as JobRecord[] | undefined) || []);
    } catch {
      setError("Connection error");
    } finally {
      inFlightRef.current = false;
    }
  }

  useEffect(() => {
    const tick = () => {
      if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
      loadJobs();
    };

    tick();
    const id = setInterval(tick, 10000);
    return () => clearInterval(id);
  }, []);

  const runningCount = jobs.filter((j) => j.status === "running" || j.status === "enqueued").length;

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-full bg-emerald-700 px-4 py-2 text-sm text-white shadow-lg transition-colors hover:bg-emerald-800"
      >
        Jobs ({jobs.length})
        {runningCount > 0 && (
          <span className="animate-pulse rounded-full bg-amber-300 px-1.5 py-0.5 text-xs font-bold text-amber-900">
            {runningCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute bottom-12 right-0 max-h-80 w-96 overflow-y-auto rounded-lg border border-stone-200 bg-white shadow-xl dark:border-stone-700 dark:bg-stone-900">
          <div className="flex items-center justify-between border-b border-stone-200 p-3 text-sm font-semibold dark:border-stone-700">
            <span>Job History</span>
            <div className="flex items-center gap-2">
              <button onClick={loadJobs} className="text-xs text-emerald-700 hover:underline dark:text-emerald-400">
                Refresh
              </button>
              <Link href="/jobs" className="text-xs text-emerald-700 hover:underline dark:text-emerald-400">
                View All
              </Link>
            </div>
          </div>
          {error ? (
            <div className="p-4 text-center text-sm text-red-600 dark:text-red-300">{error}</div>
          ) : jobs.length === 0 ? (
            <div className="p-4 text-center">
              <p className="text-sm text-stone-400">No jobs yet</p>
              <Link href="/dashboard" className="text-xs text-emerald-700 hover:underline dark:text-emerald-400">
                Start a pipeline step
              </Link>
            </div>
          ) : (
            <ul className="divide-y divide-stone-200 dark:divide-stone-700">
              {jobs.map((j) => (
                <li key={j.id} className="px-3 py-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{j.section}</span>
                    <StatusBadge status={j.status} />
                  </div>
                  <div className="mt-0.5 text-stone-500 dark:text-stone-400">
                    {j.action} &middot; {j.id?.slice(0, 8)}...
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
