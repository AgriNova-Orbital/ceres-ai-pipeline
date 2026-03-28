"use client";

import { useEffect, useState } from "react";

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

  async function loadJobs() {
    try {
      const res = await fetch("/api/jobs");
      const data = await res.json();
      setJobs(data.history || []);
    } catch { /* ignore */ }
  }

  useEffect(() => {
    loadJobs();
    const id = setInterval(loadJobs, 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <button
        onClick={() => setOpen(!open)}
        className="bg-primary text-white px-4 py-2 rounded-full shadow-lg text-sm hover:bg-primary-dark"
      >
        Jobs ({jobs.length})
      </button>
      {open && (
        <div className="absolute bottom-12 right-0 w-96 max-h-80 overflow-y-auto bg-white border rounded-lg shadow-xl">
          <div className="p-3 border-b font-semibold text-sm flex justify-between">
            <span>Job History</span>
            <button onClick={loadJobs} className="text-primary text-xs hover:underline">Refresh</button>
          </div>
          {jobs.length === 0 ? (
            <p className="p-4 text-gray-400 text-sm text-center">No jobs yet</p>
          ) : (
            <ul className="divide-y">
              {jobs.map((j) => (
                <li key={j.id} className="px-3 py-2 text-xs">
                  <div className="flex justify-between">
                    <span className="font-medium">{j.section}</span>
                    <span className={`px-1.5 py-0.5 rounded ${j.status === "enqueued" ? "bg-yellow-50 text-yellow-700" : "bg-green-50 text-green-700"}`}>
                      {j.status}
                    </span>
                  </div>
                  <div className="text-gray-400 mt-0.5">{j.action} · {j.id?.slice(0, 8)}...</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
