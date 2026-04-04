"use client";

import { useEffect, useState } from "react";

interface SystemInfo {
  cpu_count: number;
  load_avg: number[];
  disk_total_gb: number;
  disk_used_gb: number;
  disk_free_gb: number;
  disk_percent: number;
}

interface WorkerInfo {
  name: string;
  state: string;
  current_job: string | null;
}

interface QueueInfo {
  name: string;
  length: number;
}

interface RedisInfo {
  connected: boolean;
  used_memory_mb: number;
  connected_clients: number;
  uptime_days: number;
  total_commands: number;
}

interface DataInfo {
  [key: string]: { total_files: number; size_mb: number };
}

interface DatabaseInfo {
  path: string;
  exists: boolean;
  size_kb: number;
  tables: string[];
  user_count: number;
}

export default function AdminDashboard() {
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [workers, setWorkers] = useState<WorkerInfo[]>([]);
  const [queue, setQueue] = useState<QueueInfo | null>(null);
  const [redis, setRedis] = useState<RedisInfo | null>(null);
  const [data, setData] = useState<DataInfo | null>(null);
  const [db, setDb] = useState<DatabaseInfo | null>(null);
  const [error, setError] = useState("");

  async function loadAll() {
    try {
      const [sysRes, wkRes, qRes, rdRes, dtRes, dbRes] = await Promise.all([
        fetch("/api/admin/system"),
        fetch("/api/admin/workers"),
        fetch("/api/admin/queue"),
        fetch("/api/admin/redis"),
        fetch("/api/admin/data"),
        fetch("/api/admin/database"),
      ]);
      setSystem(await sysRes.json());
      const wkData = await wkRes.json();
      setWorkers(wkData.workers || []);
      setQueue(await qRes.json());
      setRedis(await rdRes.json());
      setData(await dtRes.json());
      setDb(await dbRes.json());
    } catch {
      setError("Failed to load system info");
    }
  }

  useEffect(() => {
    loadAll();
    const id = setInterval(loadAll, 10000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="min-h-screen bg-stone-50 dark:bg-stone-950">
      <header className="border-b border-stone-200 dark:border-stone-700 bg-white dark:border-stone-800 dark:bg-stone-900 px-4 sm:px-8 py-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center gap-4">
          <a href="/" className="text-emerald-700 hover:underline dark:text-emerald-400">&larr; Home</a>
          <h1 className="text-xl font-bold">Admin Dashboard</h1>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={loadAll} className="rounded border border-stone-300 px-3 py-1 text-sm hover:bg-stone-100 dark:border-stone-600 dark:hover:bg-stone-800">Refresh</button>
          <LogoutBtn />
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        {error && <div className="rounded bg-red-50 p-3 text-red-700 dark:bg-red-950/40 dark:text-red-300">{error}</div>}

        {/* System Overview */}
        <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard title="CPU Cores" value={system?.cpu_count ?? "-"} />
          <StatCard title="Load (1m)" value={system?.load_avg?.[0]?.toFixed(2) ?? "-"} />
          <StatCard
            title="Disk"
            value={system ? `${system.disk_used_gb}G / ${system.disk_total_gb}G` : "-"}
            subtitle={system ? `${system.disk_percent}% used` : ""}
          />
          <StatCard title="Redis" value={redis?.connected ? "Connected" : "Offline"} color={redis?.connected ? "green" : "red"} />
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Workers */}
          <Card title="RQ Workers" badge={workers.length.toString()}>
            {workers.length === 0 ? (
              <p className="text-stone-400 text-sm">No workers connected</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-stone-500 dark:text-stone-400 border-b border-stone-200 dark:border-stone-700">
                    <th className="pb-2">Name</th>
                    <th className="pb-2">State</th>
                    <th className="pb-2">Current Job</th>
                  </tr>
                </thead>
                <tbody>
                  {workers.map((w) => (
                    <tr key={w.name} className="border-b border-stone-200 dark:border-stone-700 last:border-0">
                      <td className="py-2 font-mono text-xs">{w.name.slice(0, 16)}...</td>
                      <td className="py-2">
                        <span className={`px-2 py-0.5 rounded text-xs ${w.state === "busy" ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200" : "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"}`}>
                          {w.state}
                        </span>
                      </td>
                      <td className="py-2 font-mono text-xs">{w.current_job || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          {/* Queue */}
          <Card title="Job Queue">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-3xl font-bold text-emerald-700 dark:text-emerald-400">{queue?.length ?? "-"}</p>
                <p className="text-sm text-stone-500 dark:text-stone-400">Pending Jobs</p>
              </div>
              <div>
                <p className="text-3xl font-bold">{queue?.name ?? "-"}</p>
                <p className="text-sm text-stone-500 dark:text-stone-400">Queue Name</p>
              </div>
            </div>
          </Card>

          {/* Redis Details */}
          <Card title="Redis">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <InfoRow label="Memory" value={redis ? `${redis.used_memory_mb} MB` : "-"} />
              <InfoRow label="Clients" value={redis?.connected_clients?.toString() ?? "-"} />
              <InfoRow label="Uptime" value={redis ? `${redis.uptime_days} days` : "-"} />
              <InfoRow label="Commands" value={redis?.total_commands?.toLocaleString() ?? "-"} />
            </div>
          </Card>

          {/* Database */}
          <Card title="Database">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <InfoRow label="Path" value={db?.path ?? "-"} />
              <InfoRow label="Size" value={db ? `${db.size_kb} KB` : "-"} />
              <InfoRow label="Tables" value={db?.tables?.join(", ") ?? "-"} />
              <InfoRow label="Users" value={db?.user_count?.toString() ?? "-"} />
            </div>
          </Card>

          {/* Data Overview */}
          <Card title="Storage" className="lg:col-span-2">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {data &&
                Object.entries(data).map(([name, info]) => (
                  <div key={name} className="text-center p-3 bg-stone-50 rounded dark:bg-stone-800">
                    <p className="text-2xl font-bold">{info.size_mb} MB</p>
                    <p className="text-sm text-stone-500 dark:text-stone-400">{name}/</p>
                    <p className="text-xs text-stone-400">{info.total_files} files</p>
                  </div>
                ))}
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}

function StatCard({ title, value, subtitle, color }: { title: string; value: string | number; subtitle?: string; color?: string }) {
  const colorClass = color === "green" ? "text-green-600" : color === "red" ? "text-red-600" : "text-stone-900 dark:text-stone-100";
  return (
    <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm dark:border-stone-700 dark:bg-stone-900">
      <p className="text-sm text-stone-500 dark:text-stone-400">{title}</p>
      <p className={`text-2xl font-bold ${colorClass}`}>{value}</p>
      {subtitle && <p className="text-xs text-stone-400">{subtitle}</p>}
    </div>
  );
}

function Card({ title, badge, children, className }: { title: string; badge?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-700 dark:bg-stone-900 ${className || ""}`}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">{title}</h2>
        {badge && <span className="text-xs bg-emerald-700 text-white px-2 py-0.5 rounded-full">{badge}</span>}
      </div>
      {children}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-stone-500 dark:text-stone-400">{label}: </span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function LogoutBtn() {
  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/login";
  }
  return (
    <button onClick={logout} className="rounded border border-stone-300 px-3 py-1 text-sm hover:bg-stone-100 dark:border-stone-600 dark:hover:bg-stone-800">
      Logout
    </button>
  );
}
