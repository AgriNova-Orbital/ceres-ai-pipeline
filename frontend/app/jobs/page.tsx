"use client";

import { useEffect, useMemo, useState } from "react";
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
  result?: Record<string, string | string[] | number> | string;
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

const sectionOrder = [
  "drive_download",
  "downloader",
  "build",
  "train",
  "eval",
  "inventory",
  "unknown",
];

const sectionLabels: Record<string, string> = {
  drive_download: "Drive Downloads",
  downloader: "Downloader",
  build: "Build Dataset",
  train: "Training",
  eval: "Evaluation",
  inventory: "Inventory",
  unknown: "Unknown",
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
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
    } catch {
      /* ignore */
    }
    setLoading(false);
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, [limit]);

  const statusCounts = {
    all: jobs.length,
    queued: jobs.filter((j) => j.status === "queued").length,
    running: jobs.filter((j) => j.status === "running").length,
    finished: jobs.filter((j) => j.status === "finished").length,
    failed: jobs.filter((j) => j.status === "failed").length,
  };

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = { all: jobs.length };
    for (const job of jobs) {
      const key = job.section || "unknown";
      counts[key] = (counts[key] || 0) + 1;
    }
    return counts;
  }, [jobs]);

  const visibleJobs = useMemo(() => {
    return jobs.filter((job) => {
      const statusOk = statusFilter === "all" ? true : job.status === statusFilter;
      const typeOk = typeFilter === "all" ? true : (job.section || "unknown") === typeFilter;
      return statusOk && typeOk;
    });
  }, [jobs, statusFilter, typeFilter]);

  const groupedJobs = useMemo(() => {
    const groups: Record<string, Job[]> = {};
    for (const job of visibleJobs) {
      const key = job.section || "unknown";
      if (!groups[key]) groups[key] = [];
      groups[key].push(job);
    }
    return sectionOrder
      .filter((key) => groups[key]?.length)
      .map((key) => ({ key, label: sectionLabels[key] || key, jobs: groups[key] }));
  }, [visibleJobs]);

  useEffect(() => {
    setCollapsedGroups((prev) => {
      const next = { ...prev };
      for (const group of groupedJobs) {
        if (typeof next[group.key] === "undefined") next[group.key] = false;
      }
      return next;
    });
  }, [groupedJobs]);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-4 sm:px-8 py-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-primary hover:underline">&larr; Home</Link>
          <h1 className="text-xl font-bold">Jobs Monitor</h1>
        </div>
        <div className="flex flex-wrap items-center gap-3">
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

        <div className="space-y-3">
          <div className="flex gap-2 flex-wrap">
            {[
              { key: "all", label: `All (${statusCounts.all})` },
              { key: "queued", label: `Queued (${statusCounts.queued})` },
              { key: "running", label: `Running (${statusCounts.running})` },
              { key: "finished", label: `Finished (${statusCounts.finished})` },
              { key: "failed", label: `Failed (${statusCounts.failed})` },
            ].map((t) => (
              <button
                key={t.key}
                onClick={() => setStatusFilter(t.key)}
                className={`px-3 py-1.5 text-sm rounded-md border ${statusFilter === t.key ? "bg-primary text-white border-primary" : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"}`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="flex gap-2 flex-wrap">
            {["all", ...sectionOrder.filter((k) => typeCounts[k])].map((key) => (
              (() => {
                const meta = getSectionMeta(key);
                return (
              <button
                key={key}
                onClick={() => setTypeFilter(key)}
                className={`px-3 py-1.5 text-sm rounded-md border flex items-center gap-2 ${typeFilter === key ? `${meta.activeClass}` : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"}`}
              >
                {key !== "all" && <span className={`inline-flex items-center justify-center min-w-8 px-1.5 py-0.5 rounded text-[10px] font-mono border ${meta.badgeClass}`}>{meta.badge}</span>}
                {key === "all" ? `All Types (${typeCounts.all || 0})` : `${sectionLabels[key] || key} (${typeCounts[key] || 0})`}
              </button>
                );
              })()
            ))}
          </div>
        </div>

        <div className="space-y-6">
          {loading ? (
            <div className="bg-white rounded-lg shadow-sm border p-8 text-center text-gray-400">Loading...</div>
          ) : groupedJobs.length === 0 ? (
            <div className="bg-white rounded-lg shadow-sm border p-8 text-center text-gray-400">No jobs found</div>
          ) : (
            groupedJobs.map((group) => (
              <section key={group.key} className="bg-white rounded-lg shadow-sm border overflow-x-auto">
                <button
                  onClick={() => setCollapsedGroups((prev) => ({ ...prev, [group.key]: !prev[group.key] }))}
                  className="w-full px-4 py-3 border-b bg-gray-50 flex items-center justify-between text-left hover:bg-gray-100"
                >
                  <div className="flex items-center gap-3">
                    <span className={`inline-flex items-center justify-center min-w-10 px-2 py-1 rounded text-[10px] font-mono border ${getSectionMeta(group.key).badgeClass}`}>
                      {getSectionMeta(group.key).badge}
                    </span>
                    <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">{group.label}</h2>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400">{group.jobs.length} jobs</span>
                    <span className="text-gray-400 text-xs">{collapsedGroups[group.key] ? "[+]" : "[-]"}</span>
                  </div>
                </button>
                {!collapsedGroups[group.key] && (
                  <div className="divide-y min-w-[860px]">
                    {group.jobs.map((j) => (
                    <div key={j.id} className="hover:bg-gray-50">
                      <button
                        onClick={() => setExpanded(expanded === j.id ? null : j.id)}
                        className="w-full px-4 py-3 flex items-center gap-4 text-left text-sm"
                      >
                        <span className="font-mono text-xs text-gray-400 w-20">{j.id.slice(0, 8)}</span>
                        <span className="w-28 flex items-center gap-2">
                          <span className={`inline-flex items-center justify-center min-w-8 px-1.5 py-0.5 rounded text-[10px] font-mono border ${getSectionMeta(j.section).badgeClass}`}>
                            {getSectionMeta(j.section).badge}
                          </span>
                          <span className="font-medium truncate">{sectionLabels[j.section] || j.section}</span>
                        </span>
                        <span className="text-gray-500 w-40 truncate">{j.action}</span>
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
                        <div className="px-4 pb-4 pl-32 space-y-3 text-sm">
                          <CommonJobDetails job={j} />
                          <JobTypeDetails job={j} />
                        </div>
                      )}
                    </div>
                    ))}
                  </div>
                )}
              </section>
            ))
          )}
        </div>
      </main>
    </div>
  );
}

function CommonJobDetails({ job }: { job: Job }) {
  return (
    <div className="space-y-2">
      {String(job.meta?.step ?? "") && (
        <InfoRow label="Current Step" value={String(job.meta?.step ?? "")} />
      )}
      {job.meta?.progress != null && Number(job.meta?.progress) > 0 && (
        <InfoRow label="Progress" value={`${Number(job.meta?.progress)}%`} />
      )}
      {job.started_at && <InfoRow label="Started" value={formatTime(job.started_at)} />}
      {job.ended_at && <InfoRow label="Ended" value={formatTime(job.ended_at)} />}
    </div>
  );
}

function JobTypeDetails({ job }: { job: Job }) {
  const resultObj = typeof job.result === "string" ? null : (job.result || null);

  if (job.section === "drive_download") {
    return <DriveJobDetails job={job} resultObj={resultObj} />;
  }

  if (["downloader", "build", "train", "eval", "inventory"].includes(job.section)) {
    return <ScriptJobDetails job={job} resultObj={resultObj} />;
  }

  return <GenericJobDetails job={job} />;
}

function DriveJobDetails({ job, resultObj }: { job: Job; resultObj: Record<string, string | string[] | number> | null }) {
  const currentFile = String(job.meta?.current_file ?? "");
  const filesDone = job.meta?.files_done != null ? Number(job.meta.files_done) : null;
  const totalFiles = job.meta?.total_files != null ? Number(job.meta.total_files) : null;
  const speedBps = job.meta?.speed_bps != null ? Number(job.meta.speed_bps) : null;
  const etaSeconds = job.meta?.eta_seconds != null ? Number(job.meta.eta_seconds) : null;
  const bytesDone = job.meta?.bytes_done != null ? Number(job.meta.bytes_done) : null;
  const totalBytes = job.meta?.total_bytes != null ? Number(job.meta.total_bytes) : null;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {currentFile && <InfoRow label="Current File" value={currentFile} />}
        {filesDone != null && totalFiles != null && (
          <InfoRow label="Files" value={`${filesDone}/${totalFiles}`} />
        )}
        {speedBps != null && <InfoRow label="Speed" value={formatSpeed(speedBps)} />}
        {etaSeconds != null && <InfoRow label="ETA" value={formatEta(etaSeconds)} />}
        {bytesDone != null && totalBytes != null && (
          <InfoRow label="Bytes" value={`${formatBytes(bytesDone)} / ${formatBytes(totalBytes)}`} />
        )}
      </div>

      {resultObj && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {resultObj.downloaded != null && <InfoRow label="Downloaded" value={String(resultObj.downloaded)} />}
          {resultObj.total_size != null && <InfoRow label="Total Size" value={formatBytes(Number(resultObj.total_size))} />}
          {Array.isArray(resultObj.merged_weeks) && <InfoRow label="Merged Weeks" value={String(resultObj.merged_weeks.length)} />}
          {Array.isArray(resultObj.single_tile_weeks_normalized) && <InfoRow label="Normalized Weeks" value={String(resultObj.single_tile_weeks_normalized.length)} />}
          {Array.isArray(resultObj.failed_weeks) && <InfoRow label="Failed Weeks" value={String(resultObj.failed_weeks.length)} />}
          {Array.isArray(resultObj.unknown_files) && <InfoRow label="Unknown Files" value={String(resultObj.unknown_files.length)} />}
        </div>
      )}

      {job.error && <ErrorBlock error={job.error} />}
      {resultObj && <JsonBlock title="Result" value={resultObj} />}
    </div>
  );
}

function ScriptJobDetails({ job, resultObj }: { job: Job; resultObj: Record<string, string | string[] | number> | null }) {
  return (
    <div className="space-y-3">
      {resultObj?.cmd && (
        <div>
          <p className="text-gray-500 text-xs font-medium mb-1">Command</p>
          <pre className="bg-gray-50 p-2 rounded text-xs overflow-x-auto whitespace-pre-wrap">{Array.isArray(resultObj.cmd) ? resultObj.cmd.join(" ") : String(resultObj.cmd)}</pre>
        </div>
      )}
      {resultObj?.cwd && <InfoRow label="Working Dir" value={String(resultObj.cwd)} />}
      {typeof resultObj?.returncode !== "undefined" && <InfoRow label="Return Code" value={String(resultObj.returncode)} />}
      {resultObj?.stdout && <TextBlock title="stdout" value={String(resultObj.stdout)} />}
      {resultObj?.stderr && <TextBlock title="stderr" value={String(resultObj.stderr)} danger />}
      {job.error && <ErrorBlock error={job.error} />}
      {!resultObj && job.result && <JsonBlock title="Result" value={job.result} />}
    </div>
  );
}

function GenericJobDetails({ job }: { job: Job }) {
  return (
    <div className="space-y-3">
      {job.result && <JsonBlock title="Result" value={job.result} />}
      {job.error && <ErrorBlock error={job.error} />}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${statusColors[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

function getSectionMeta(section: string) {
  const map: Record<string, { badge: string; badgeClass: string; activeClass: string }> = {
    drive_download: {
      badge: "DRV",
      badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
      activeClass: "bg-emerald-600 text-white border-emerald-600",
    },
    downloader: {
      badge: "DLD",
      badgeClass: "bg-sky-50 text-sky-700 border-sky-200",
      activeClass: "bg-sky-600 text-white border-sky-600",
    },
    build: {
      badge: "BLD",
      badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
      activeClass: "bg-amber-600 text-white border-amber-600",
    },
    train: {
      badge: "TRN",
      badgeClass: "bg-violet-50 text-violet-700 border-violet-200",
      activeClass: "bg-violet-600 text-white border-violet-600",
    },
    eval: {
      badge: "EVL",
      badgeClass: "bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200",
      activeClass: "bg-fuchsia-600 text-white border-fuchsia-600",
    },
    inventory: {
      badge: "INV",
      badgeClass: "bg-cyan-50 text-cyan-700 border-cyan-200",
      activeClass: "bg-cyan-600 text-white border-cyan-600",
    },
    unknown: {
      badge: "???",
      badgeClass: "bg-gray-50 text-gray-700 border-gray-200",
      activeClass: "bg-gray-700 text-white border-gray-700",
    },
    all: {
      badge: "ALL",
      badgeClass: "bg-gray-50 text-gray-700 border-gray-200",
      activeClass: "bg-slate-900 text-white border-slate-900",
    },
  };
  return map[section] || map.unknown;
}

function ProgressBar({ pct, step }: { pct: number; step?: string }) {
  return (
    <div className="flex items-center gap-2 flex-1 max-w-xs">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="text-xs text-gray-500 whitespace-nowrap">{pct}%</span>
      {step && <span className="text-xs text-gray-400 truncate max-w-24">{step}</span>}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 flex-wrap">
      <span className="text-gray-500 text-xs w-24">{label}:</span>
      <span className="text-gray-800 text-xs break-all">{value}</span>
    </div>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <div>
      <p className="text-gray-500 text-xs font-medium mb-1">{title}</p>
      <pre className="bg-gray-50 p-2 rounded text-xs overflow-x-auto max-h-48 whitespace-pre-wrap">{typeof value === "string" ? value : JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}

function TextBlock({ title, value, danger = false }: { title: string; value: string; danger?: boolean }) {
  return (
    <div>
      <p className={`text-xs font-medium mb-1 ${danger ? "text-red-600" : "text-gray-500"}`}>{title}</p>
      <pre className={`${danger ? "bg-red-50 text-red-700" : "bg-gray-50 text-gray-800"} p-2 rounded text-xs overflow-x-auto max-h-40 whitespace-pre-wrap`}>
        {value}
      </pre>
    </div>
  );
}

function ErrorBlock({ error }: { error: string }) {
  return <TextBlock title="Error" value={error} danger />;
}

function formatTime(iso: string): string {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("zh-TW", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return iso;
  }
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const mib = bytes / (1024 * 1024);
  if (mib >= 1024) return `${(mib / 1024).toFixed(2)} GiB`;
  if (mib >= 1) return `${mib.toFixed(2)} MiB`;
  const kib = bytes / 1024;
  if (kib >= 1) return `${kib.toFixed(1)} KiB`;
  return `${bytes.toFixed(0)} B`;
}

function formatSpeed(speedBps: number): string {
  if (!Number.isFinite(speedBps) || speedBps <= 0) return "0 B/s";
  const mib = speedBps / (1024 * 1024);
  if (mib >= 1) return `${mib.toFixed(2)} MiB/s`;
  const kib = speedBps / 1024;
  if (kib >= 1) return `${kib.toFixed(1)} KiB/s`;
  return `${speedBps.toFixed(0)} B/s`;
}

function formatEta(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0s";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}
