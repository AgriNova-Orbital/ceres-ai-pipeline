"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";

interface DriveFile {
  id: string;
  name: string;
  size_mb: number;
  mimeType: string;
  modifiedTime?: string;
}

interface DownloadItem {
  id: string;
  name: string;
  size: number;
  progress: number;
  status: string;
  message: string;
  jobId?: string;
}

export default function DrivePage() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [error, setError] = useState("");
  const [folderId, setFolderId] = useState("root");
  const [folderPath, setFolderPath] = useState<{ id: string; name: string }[]>([{ id: "root", name: "My Drive" }]);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [folderCount, setFolderCount] = useState(0);
  const [fileCount, setFileCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const [logLines, setLogLines] = useState<string[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  function addLog(line: string) {
    setLogLines((prev) => {
      const next = [...prev, `[${new Date().toLocaleTimeString()}] ${line}`];
      return next.slice(-100);
    });
  }

  async function checkStatus() {
    try {
      const res = await fetch("/api/oauth/status");
      const data = await res.json();
      setConfigured(data.configured);
      if (data.configured) listFolder("root", "My Drive");
    } catch { setConfigured(false); }
  }

  async function listFolder(id: string, name?: string) {
    setLoading(true);
    setFolderId(id);
    try {
      const res = await fetch(`/api/drive/list?id=${id}`);
      if (res.ok) {
        const data = await res.json();
        const allItems = [...(data.folders || []), ...(data.files || [])];
        setFiles(allItems);
        setTotalCount(data.total || allItems.length);
        setFolderCount(data.folder_count || (data.folders || []).length);
        setFileCount(data.file_count || (data.files || []).length);
        setError("");
        setSelected(new Set());
      } else {
        const data = await res.json();
        setError(data.error || "Failed");
      }
    } catch { setError("Connection error"); }
    setLoading(false);
  }

  function navigateTo(id: string, name: string) {
    const idx = folderPath.findIndex((p) => p.id === id);
    if (idx >= 0) setFolderPath(folderPath.slice(0, idx + 1));
    else setFolderPath([...folderPath, { id, name }]);
    listFolder(id, name);
  }

  function toggleSelect(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
  }

  async function handleDownload(items: { id: string; name: string; size: number }[]) {
    const newItems: DownloadItem[] = items.map((f) => ({
      id: f.id, name: f.name, size: f.size, progress: 0, status: "queued", message: "waiting",
    }));
    setDownloads((prev) => [...prev, ...newItems]);
    addLog(`Starting download of ${items.length} file(s)...`);

    for (const item of items) {
      try {
        const res = await fetch("/api/drive/download", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ folder_id: item.id, save_dir: `data/raw/drive_download` }),
        });
        const data = await res.json();
        if (data.job_id) {
          setDownloads((prev) => prev.map((d) => d.id === item.id ? { ...d, jobId: data.job_id, status: "submitted" } : d));
          addLog(`Queued: ${item.name} (job: ${data.job_id.slice(0, 8)})`);
        }
      } catch {
        setDownloads((prev) => prev.map((d) => d.id === item.id ? { ...d, status: "error", message: "submit failed" } : d));
        addLog(`Error: ${item.name}`);
      }
    }
  }

  // Poll jobs for progress
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const res = await fetch("/api/jobs");
        const data = await res.json();
        const jobs = data.jobs || [];
        setDownloads((prev) =>
          prev.map((d) => {
            if (!d.jobId) return d;
            const job = jobs.find((j: { id: string }) => j.id === d.jobId);
            if (job) {
              const prog = Number(job.meta?.progress ?? (job.status === "finished" ? 100 : 0));
              const step = String(job.meta?.step ?? job.status);
              return { ...d, status: job.status, progress: prog, message: step };
            }
            return d;
          })
        );
      } catch { /* */ }
    }, 2000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => { checkStatus(); }, []);

  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight);
  }, [logLines]);

  const total = downloads.length;
  const done = downloads.filter((d) => d.status === "finished" || d.status === "failed" || d.status === "error").length;
  const active = downloads.filter((d) => d.status === "running").length;

  return (
    <div className="min-h-screen bg-gray-50 font-mono">
      <header className="bg-white border-b px-8 py-4 flex justify-between items-center font-sans">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-primary hover:underline">&larr; Home</Link>
          <h1 className="text-xl font-bold">Google Drive</h1>
        </div>
        <LogoutButton />
      </header>

      <div className="max-w-7xl mx-auto p-6 flex gap-6">
        {/* Left: File Browser */}
        <div className="flex-1 space-y-4">
          {error && <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm font-sans">{error}</div>}

          {/* Upload (not configured) */}
          {configured === false && (
            <div className="bg-white rounded-lg shadow-sm border p-6 space-y-4 font-sans">
              <h2 className="text-lg font-semibold">Upload client_secret.json</h2>
              <form onSubmit={async (e) => {
                e.preventDefault();
                if (!uploadFile) return;
                const form = new FormData();
                form.append("file", uploadFile);
                form.append("redirect_base_url", typeof window !== "undefined" ? window.location.origin : "");
                const res = await fetch("/api/oauth/upload-secret", { method: "POST", body: form });
                if (res.ok) { setConfigured(true); addLog("OAuth configured"); listFolder("root"); }
              }} className="flex gap-2 items-end">
                <label className="flex-1">
                  <input type="file" accept=".json" onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    className="block w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-primary file:text-white" />
                </label>
                <button type="submit" className="px-4 py-2 bg-primary text-white rounded text-sm">Upload</button>
              </form>
            </div>
          )}

          {/* Connect */}
          {configured && files.length === 0 && !loading && (
            <div className="bg-white rounded-lg shadow-sm border p-8 text-center font-sans">
              <button onClick={() => window.location.href = "/api/oauth/login"}
                className="px-6 py-3 bg-primary text-white rounded-md hover:bg-primary-dark font-medium">
                Connect to Google Drive
              </button>
            </div>
          )}

          {/* Browser */}
          {configured && (
            <>
              {/* Toolbar */}
              <div className="bg-white rounded-lg shadow-sm border p-2 flex items-center gap-2 text-sm font-sans">
              <span className="px-2 text-xs text-gray-500">{folderCount} folders / {fileCount} files</span>
                <input value={folderId} onChange={(e) => setFolderId(e.target.value)}
                  placeholder="Folder ID" className="flex-1 px-2 py-1 border rounded text-xs" />
                <button onClick={() => listFolder(folderId)} disabled={loading}
                  className="px-3 py-1 bg-primary text-white rounded text-xs disabled:opacity-50">
                  {loading ? "..." : "Go"}
                </button>
                <button onClick={() => window.location.href = "/api/oauth/login"}
                  className="px-3 py-1 border rounded text-xs hover:bg-gray-50">Re-auth</button>
                {selected.size > 0 && (
                  <button onClick={() => handleDownload(files.filter((f) => selected.has(f.id)).map((f) => ({ id: f.id, name: f.name, size: f.size_mb })))}
                    className="px-3 py-1 bg-green-600 text-white rounded text-xs">
                    Download ({selected.size})
                  </button>
                )}
              </div>

              {/* Breadcrumb */}
              <div className="flex items-center gap-1 text-xs text-gray-500">
                {folderPath.map((p, i) => (
                  <span key={p.id} className="flex items-center gap-1">
                    {i > 0 && <span>/</span>}
                    <button onClick={() => navigateTo(p.id, p.name)}
                      className={i === folderPath.length - 1 ? "text-gray-900 font-bold" : "text-primary hover:underline"}>
                      {p.name}
                    </button>
                  </span>
                ))}
              </div>

              {/* Table */}
              <div className="bg-black text-green-400 rounded-lg shadow-lg overflow-hidden text-xs">
                <div className="px-3 py-1.5 bg-gray-900 border-b border-gray-700 text-gray-400 flex gap-4">
                  <span className="w-4"><input type="checkbox" checked={selected.size === files.length && files.length > 0}
                    onChange={() => { if (selected.size === files.length) setSelected(new Set()); else setSelected(new Set(files.map((f) => f.id))); }} /></span>
                  <span className="w-96">Name</span>
                  <span className="w-20">Size</span>
                  <span className="w-24">Modified</span>
                  <span className="w-16">Action</span>
                </div>
                <div className="max-h-96 overflow-y-auto">
                  {files.length === 0 && !loading && <div className="px-3 py-4 text-gray-500 text-center">empty</div>}
                  {files.map((f) => {
                    const isFolder = f.mimeType === "application/vnd.google-apps.folder";
                    return (
                      <div key={f.id}
                        className={`px-3 py-1 flex gap-4 hover:bg-gray-800 ${selected.has(f.id) ? "bg-gray-800" : ""} border-b border-gray-800 last:border-0`}>
                        <span className="w-4"><input type="checkbox" checked={selected.has(f.id)} onChange={() => toggleSelect(f.id)} /></span>
                        <span className="w-96 truncate">
                          {isFolder ? (
                            <button onClick={() => navigateTo(f.id, f.name)} className="text-yellow-400 hover:underline">
                              {f.name}/
                            </button>
                          ) : (
                            <span>{f.name}</span>
                          )}
                        </span>
                        <span className="w-20 text-gray-500">{f.size_mb > 0 ? `${f.size_mb}M` : "-"}</span>
                        <span className="w-24 text-gray-500">{f.modifiedTime ? new Date(f.modifiedTime).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "-"}</span>
                        <span className="w-16">
                          {!isFolder && (
                            <button onClick={() => handleDownload([{ id: f.id, name: f.name, size: f.size_mb }])}
                              className="text-green-400 hover:text-green-300">dl</button>
                          )}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}

          {configured === null && <p className="text-center text-gray-400 p-8 font-sans">Loading...</p>}
        </div>

        {/* Right: Pacman-style Terminal */}
        <div className="w-96 flex-shrink-0 space-y-4">
          {/* Download Progress */}
          {downloads.length > 0 && (
            <div className="bg-black text-green-400 rounded-lg shadow-lg overflow-hidden text-xs">
              <div className="px-3 py-2 bg-gray-900 border-b border-gray-700 flex justify-between items-center">
                <span className="text-gray-300 font-bold">
                  :: Installing packages ({done}/{total})
                </span>
                <button onClick={() => setDownloads([])} className="text-gray-500 hover:text-gray-300">clear</button>
              </div>
              <div className="p-3 space-y-1.5 max-h-80 overflow-y-auto">
                {downloads.map((d, i) => {
                  const barLen = 25;
                  const filled = Math.round((d.progress / 100) * barLen);
                  const bar = "#".repeat(filled) + "-".repeat(barLen - filled);
                  const statusIcon =
                    d.status === "finished" ? "\u2713" :
                    d.status === "error" || d.status === "failed" ? "\u2717" :
                    d.status === "running" ? ">" : " ";

                  return (
                    <div key={`${d.id}-${i}`}>
                      <span className="text-gray-500">({i + 1}/{total}) </span>
                      <span className="text-gray-300">{d.name.slice(0, 35).padEnd(35)}</span>
                    </div>
                  );
                })}
                {/* Active progress bar */}
                {downloads.filter((d) => d.status === "running" || d.status === "queued" || d.status === "submitted").slice(0, 1).map((d) => {
                  const barLen = 25;
                  const filled = Math.round((d.progress / 100) * barLen);
                  const bar = "\u2588".repeat(filled) + "\u2591".repeat(barLen - filled);
                  return (
                    <div key={`active-${d.id}`} className="mt-1">
                      <span className="text-green-300">{bar}</span>
                      <span className="text-yellow-400 ml-2">{d.progress}%</span>
                      <span className="text-gray-500 ml-2">{d.message}</span>
                    </div>
                  );
                })}
                {/* Finished items */}
                {downloads.filter((d) => d.status === "finished").map((d, i) => (
                  <div key={`done-${d.id}-${i}`} className="text-gray-500">
                    <span className="text-green-400">::</span> {d.name.slice(0, 30)} installed
                  </div>
                ))}
                {/* Failed items */}
                {downloads.filter((d) => d.status === "failed" || d.status === "error").map((d, i) => (
                  <div key={`err-${d.id}-${i}`} className="text-red-400">
                    <span>::</span> {d.name.slice(0, 30)} failed: {d.message}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Activity Log */}
          <div className="bg-black text-gray-400 rounded-lg shadow-lg overflow-hidden text-xs">
            <div className="px-3 py-2 bg-gray-900 border-b border-gray-700 text-gray-300 font-bold">
              :: Activity Log
            </div>
            <div ref={logRef} className="p-3 h-64 overflow-y-auto space-y-0.5">
              {logLines.length === 0 && <div className="text-gray-600">waiting for activity...</div>}
              {logLines.map((line, i) => (
                <div key={i} className={line.includes("Error") ? "text-red-400" : ""}>{line}</div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
