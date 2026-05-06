"use client";

import { useEffect, useRef, useState } from "react";
import StatusBadge from "@/components/StatusBadge";
import { readApiResponse } from "@/lib/api-response";
import { jobProgressLabel, jobResultSummary } from "@/lib/job-detail";

interface JobDetailCardProps {
  jobId: string | null;
}

export default function JobDetailCard({ jobId }: JobDetailCardProps) {
  const [job, setJob] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const inFlightRef = useRef(false);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      setError("");
      return;
    }

    async function load() {
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      try {
        const res = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
        const response = await readApiResponse(res, "Failed to load job detail");
        if (response.ok) {
          setError("");
          setJob((response.data.job as Record<string, unknown> | undefined) || null);
        } else {
          setError(response.error);
        }
      } catch {
        setError("Connection error");
      } finally {
        inFlightRef.current = false;
      }
    }

    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [jobId]);

  if (!jobId) return null;

  return (
    <section className="rounded-lg border border-stone-200 bg-white p-4 text-sm shadow-sm dark:border-stone-700 dark:bg-stone-900">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold text-stone-900 dark:text-stone-100">Latest Job</h2>
        {typeof job?.status === "string" && <StatusBadge status={job.status} />}
      </div>
      <p className="mt-2 font-mono text-xs text-stone-500 dark:text-stone-400">{jobId}</p>
      {error ? <p className="mt-3 text-red-600 dark:text-red-300">{error}</p> : null}
      {job ? (
        <>
          <p className="mt-3 text-stone-600 dark:text-stone-300">{jobProgressLabel(job)}</p>
          <pre className="mt-3 max-h-48 overflow-auto rounded bg-stone-950 p-3 text-xs text-stone-100">
            {jobResultSummary(job)}
          </pre>
        </>
      ) : (
        <p className="mt-3 text-stone-400">Loading job detail...</p>
      )}
    </section>
  );
}
