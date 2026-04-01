"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import StatusBadge from "@/components/StatusBadge";

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
  const inFlightRef = useRef(false);

  async function loadJobs() {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    try {
      const res = await fetch("/api/jobs", { cache: "no-store" });
      const data = await res.json();
      setJobs(data.history || []);
    } catch {
      /* ignore */
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
        className="bg-primary text-white px-4 py-2 rounded-full shadow-lg text-sm hover:bg-primary-dark transition-colors flex items-center gap-2"
      >
        Jobs ({jobs.length})
        {runningCount > 0 && (
          <span className="bg-yellow-400 text-yellow-900 text-xs font-bold px-1.5 py-0.5 rounded-full animate-pulse">
            {runningCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute bottom-12 right-0 w-96 max-h-80 overflow-y-auto bg-white border rounded-lg shadow-xl">
          <div className="p-3 border-b font-semibold text-sm flex justify-between items-center">
            <span>Job History</span>
            <div className="flex items-center gap-2">
              <button
                onClick={loadJobs}
                className="text-primary text-xs hover:underline"
              >
                Refresh
              </button>
              <Link
                href="/jobs"
                className="text-primary text-xs hover:underline"
              >
                View All
              </Link>
            </div>
          </div>
          {jobs.length === 0 ? (
            <div className="p-4 text-center">
              <p className="text-gray-400 text-sm">No jobs yet</p>
              <Link href="/" className="text-xs text-primary hover:underline">
                Start a pipeline step
              </Link>
            </div>
          ) : (
            <ul className="divide-y">
              {jobs.map((j) => (
                <li key={j.id} className="px-3 py-2 text-xs">
                  <div className="flex justify-between items-center">
                    <span className="font-medium">{j.section}</span>
                    <StatusBadge status={j.status} />
                  </div>
                  <div className="text-gray-400 mt-0.5">
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
