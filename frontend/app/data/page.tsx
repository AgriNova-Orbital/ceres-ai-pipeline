"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";
import { summarizeWeekRange } from "@/lib/week-range";

interface FileInfo {
  path: string;
  name: string;
  size_mb: number;
  dir?: string;
}

interface RunEntry {
  name: string;
  files: number;
  size_mb: number;
}

export default function DataPage() {
  const [tab, setTab] = useState("raw");
  const [rawFiles, setRawFiles] = useState<FileInfo[]>([]);
  const [patches, setPatches] = useState<FileInfo[]>([]);
  const [reports, setReports] = useState<FileInfo[]>([]);
  const [runs, setRuns] = useState<RunEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [onlyRange, setOnlyRange] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [r1, r2, r3, r4] = await Promise.all([
        fetch("/api/scan/raw?limit=500"),
        fetch("/api/scan/patches?limit=500"),
        fetch("/api/scan/reports"),
        fetch("/api/scan/runs"),
      ]);
      setRawFiles((await r1.json()).files || []);
      setPatches((await r2.json()).files || []);
      setReports((await r3.json()).files || []);
      setRuns((await r4.json()).runs || []);
    } catch { /* ignore */ }
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  const tabs = [
    { key: "raw", label: `Raw GeoTIFFs (${rawFiles.length})` },
    { key: "patches", label: `Patches (${patches.length})` },
    { key: "runs", label: `Runs (${runs.length})` },
    { key: "reports", label: `Reports (${reports.length})` },
  ];

  const totalSize = [
    rawFiles.reduce((s, f) => s + f.size_mb, 0),
    patches.reduce((s, f) => s + f.size_mb, 0),
    runs.reduce((s, r) => s + r.size_mb, 0),
  ];
  const rangeSummary = summarizeWeekRange(rawFiles, rangeStart, rangeEnd, (f) => f.name, (f) => f.size_mb || 0);
  const visibleRawFiles = onlyRange && rangeStart && rangeEnd ? rangeSummary.selected : rawFiles;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-8 py-4 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-primary hover:underline">&larr; Home</Link>
          <h1 className="text-xl font-bold">Data Browser</h1>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={load} className="text-sm px-3 py-1 border rounded hover:bg-gray-50">Rescan</button>
          <LogoutButton />
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Summary */}
        <div className="grid grid-cols-4 gap-4">
          <StatCard title="Raw GeoTIFFs" value={rawFiles.length} unit={`(${totalSize[0].toFixed(0)} MB)`} />
          <StatCard title="Patch Files" value={patches.length} unit={`(${totalSize[1].toFixed(0)} MB)`} />
          <StatCard title="Run Results" value={runs.length} unit={`(${totalSize[2].toFixed(0)} MB)`} />
          <StatCard title="Reports" value={reports.length} unit="" />
        </div>

        {/* Tabs */}
        <div className="flex gap-2">
          {tabs.map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`px-3 py-1.5 text-sm rounded-md border ${tab === t.key ? "bg-primary text-white border-primary" : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"}`}>
              {t.label}
            </button>
          ))}
        </div>

        {tab === "raw" && (
          <div className="bg-white rounded-lg shadow-sm border p-3 flex items-center gap-2 text-sm">
            <span className="text-gray-500 text-xs">Week Range</span>
            <input
              value={rangeStart}
              onChange={(e) => setRangeStart(e.target.value.toUpperCase())}
              placeholder="2020W53"
              className="w-28 px-2 py-1 border rounded text-xs"
            />
            <span className="text-xs text-gray-400">~</span>
            <input
              value={rangeEnd}
              onChange={(e) => setRangeEnd(e.target.value.toUpperCase())}
              placeholder="2021W10"
              className="w-28 px-2 py-1 border rounded text-xs"
            />
            <button onClick={() => setOnlyRange((v) => !v)} className="px-2 py-1 border rounded text-xs hover:bg-gray-50">
              {onlyRange ? "Show All" : "Only Range"}
            </button>
            {(rangeStart && rangeEnd) && (
              <span className="text-xs text-gray-500 ml-2">
                {rangeSummary.weekCount} weeks / {rangeSummary.fileCount} files / {rangeSummary.totalSizeMb.toFixed(1)} MB
              </span>
            )}
          </div>
        )}

        {/* Content */}
        <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
          {loading ? <p className="p-8 text-center text-gray-400">Scanning...</p> : (
            <>
              {tab === "raw" && <FileTable files={visibleRawFiles} />}
              {tab === "patches" && <FileTable files={patches} />}
              {tab === "runs" && <RunsTable runs={runs} />}
              {tab === "reports" && <FileTable files={reports} />}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function StatCard({ title, value, unit }: { title: string; value: number; unit: string }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border p-4">
      <p className="text-sm text-gray-500">{title}</p>
      <p className="text-2xl font-bold">{value}</p>
      {unit && <p className="text-xs text-gray-400">{unit}</p>}
    </div>
  );
}

function FileTable({ files }: { files: FileInfo[] }) {
  if (files.length === 0) return <p className="p-8 text-center text-gray-400">No files found</p>;
  // Group by directory
  const groups: Record<string, FileInfo[]> = {};
  for (const f of files) {
    const dir = f.dir || f.path.split("/").slice(0, -1).join("/");
    if (!groups[dir]) groups[dir] = [];
    groups[dir].push(f);
  }
  return (
    <div className="divide-y">
      {Object.entries(groups).map(([dir, group]) => (
        <div key={dir}>
          <div className="px-4 py-2 bg-gray-50 text-xs font-medium text-gray-500 flex justify-between">
            <span>{dir}/</span>
            <span>{group.length} files · {group.reduce((s, f) => s + f.size_mb, 0).toFixed(1)} MB</span>
          </div>
          <div className="divide-y">
            {group.slice(0, 20).map((f) => (
              <div key={f.path} className="px-4 py-1.5 flex justify-between text-sm">
                <span className="font-mono text-xs text-gray-700 truncate">{f.name}</span>
                <span className="text-gray-400 text-xs whitespace-nowrap">{f.size_mb} MB</span>
              </div>
            ))}
            {group.length > 20 && (
              <div className="px-4 py-1.5 text-xs text-gray-400 italic">...and {group.length - 20} more</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function RunsTable({ runs }: { runs: RunEntry[] }) {
  if (runs.length === 0) return <p className="p-8 text-center text-gray-400">No runs found</p>;
  return (
    <table className="w-full text-sm">
      <thead className="bg-gray-50 border-b"><tr className="text-left text-gray-500">
        <th className="px-4 py-3">Run</th>
        <th className="px-4 py-3">Files</th>
        <th className="px-4 py-3">Size</th>
      </tr></thead>
      <tbody className="divide-y">
        {runs.map((r) => (
          <tr key={r.name} className="hover:bg-gray-50">
            <td className="px-4 py-2 font-mono text-xs">{r.name}</td>
            <td className="px-4 py-2">{r.files}</td>
            <td className="px-4 py-2">{r.size_mb} MB</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
