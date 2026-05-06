interface JobLike {
  meta?: Record<string, unknown>;
  result?: Record<string, unknown> | string;
  error?: string;
}

export function jobProgressLabel(job: JobLike): string {
  const step = typeof job.meta?.step === "string" ? job.meta.step : "Waiting for worker";
  const progress = typeof job.meta?.progress === "number" ? ` (${job.meta.progress}%)` : "";
  return `${step}${progress}`;
}

export function jobResultSummary(job: JobLike): string {
  if (job.error) return job.error;
  if (typeof job.result === "string") return job.result;
  if (job.result && typeof job.result.stderr === "string" && job.result.stderr) return job.result.stderr;
  if (job.result && typeof job.result.stdout === "string" && job.result.stdout) return job.result.stdout;
  if (job.result) return JSON.stringify(job.result);
  return "No result yet";
}
