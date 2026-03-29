"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";

interface DriveFile {
  id: string;
  name: string;
  size_mb: number;
  size_bytes?: number;
  mimeType: string;
  modifiedTime?: string;
}

interface DownloadJob {
  id: string;
  fileName: string;
  status: string;
  progress: number;
  message: string;
}

export default function DrivePage() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [error, setError] = useState("");
  const [folderId, setFolderId] = useState("root");
  const [folderName, setFolderName] = useState("My Drive");
  const [folderPath, setFolderPath] = useState<{ id: string; name: string }[]>([{ id: "root", name: "My Drive" }]);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadMsg, setUploadMsg] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [downloads, setDownloads] = useState<DownloadJob[]>([]);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  async function checkStatus() {
    try {
      const res = await fetch("/api/oauth/status");
      const data = await res.json();
      setConfigured(data.configured);
      if (data.configured) {
        listFolder("root", "My Drive");
      }
    } catch {
      setConfigured(false);
    }
  }

  async function listFolder(id: string, name?: string) {
    setLoading(true);
    setFolderId(id);
    if (name) setFolderName(name);
    try {
      const res = await fetch(`/api/drive/list?id=${id}`);
      if (res.ok) {
        const data = await res.json();
        setFiles(data.files || []);
        setError("");
        setSelected(new Set());
      } else {
        const data = await res.json();
        setError(data.error || "Failed to list files");
      }
    } catch {
      setError("Connection error");
    }
    setLoading(false);
  }

  function navigateTo(id: string, name: string) {
    // Update breadcrumb
    const idx = folderPath.findIndex((p) => p.id === id);
    if (idx >= 0) {
      setFolderPath(folderPath.slice(0, idx + 1));
    } else {
      setFolderPath([...folderPath, { id, name }]);
    }
    listFolder(id, name);
  }

  function toggleSelect(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  }

  function selectAll() {
    if (selected.size === files.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(files.map((f) => f.id)));
    }
  }

  async function handleDownload(file: DriveFile) {
    const job: DownloadJob = {
      id: file.id,
      fileName: file.name,
      status: "queued",
      progress: 0,
      message: "Starting...",
    };
    setDownloads((prev) => [...prev, job]);

    try {
      const res = await fetch("/api/drive/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          folder_id: file.id,
          save_dir: `data/raw/drive_download/${file.name}`,
        }),
      });
      const data = await res.json();
      if (data.job_id) {
        setDownloads((prev) =>
          prev.map((d) => (d.id === file.id ? { ...d, id: data.job_id, status: "submitted", message: "Queued in worker" } : d))
        );
      }
    } catch {
      setDownloads((prev) =>
        prev.map((d) => (d.id === file.id ? { ...d, status: "error", message: "Submit failed" } : d))
      );
    }
  }

  async function handleDownloadSelected() {
    for (const f of files.filter((f) => selected.has(f.id))) {
      await handleDownload(f);
    }
  }

  // Poll download progress
  useEffect(() => {
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch("/api/jobs");
        const data = await res.json();
        const jobs = data.jobs || [];

        setDownloads((prev) =>
          prev.map((d) => {
            const job = jobs.find((j: { id: string }) => j.id === d.id);
            if (job) {
              return {
                ...d,
                status: job.status,
                progress: Number(job.meta?.progress ?? 0),
                message: String(job.meta?.step ?? job.status),
              };
            }
            return d;
          })
        );
      } catch { /* ignore */ }
    }, 2000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  useEffect(() => { checkStatus(); }, []);

  const folders = files.filter((f) => f.mimeType === "application/vnd.google-apps.folder");
  const fileItems = files.filter((f) => f.mimeType !== "application/vnd.google-apps.folder");

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-8 py-4 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-primary hover:underline">&larr; Home</Link>
          <h1 className="text-xl font-bold">Google Drive</h1>
        </div>
        <LogoutButton />
      </header>

      <main className="max-w-7xl mx-auto p-6 space-y-4">
        {error && <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm">{error}</div>}
        {uploadMsg && <div className="p-3 bg-green-50 border border-green-200 text-green-700 rounded text-sm">{uploadMsg}</div>}

        {/* Not configured */}
        {configured === false && (
          <div className="bg-white rounded-lg shadow-sm border p-6 space-y-4">
            <h2 className="text-lg font-semibold">Upload client_secret.json</h2>
            <form onSubmit={async (e) => {
              e.preventDefault();
              if (!uploadFile) return;
              const form = new FormData();
              form.append("file", uploadFile);
              form.append("redirect_base_url", typeof window !== "undefined" ? window.location.origin : "");
              const res = await fetch("/api/oauth/upload-secret", { method: "POST", body: form });
              if (res.ok) { setUploadMsg("Uploaded!"); setConfigured(true); }
            }} className="flex gap-2 items-end">
              <label className="flex-1">
                <span className="text-sm font-medium text-gray-700">client_secret.json</span>
                <input type="file" accept=".json" onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="mt-1 block w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:bg-primary file:text-white" />
              </label>
              <button type="submit" className="px-4 py-2 bg-primary text-white rounded-md text-sm">Upload</button>
            </form>
          </div>
        )}

        {/* Connect button */}
        {configured && files.length === 0 && !loading && (
          <div className="bg-white rounded-lg shadow-sm border p-8 text-center space-y-4">
            <button onClick={() => window.location.href = "/api/oauth/login"}
              className="px-6 py-3 bg-primary text-white rounded-md hover:bg-primary-dark font-medium">
              Connect to Google Drive
            </button>
          </div>
        )}

        {/* File Browser */}
        {configured && (
          <>
            {/* Toolbar */}
            <div className="bg-white rounded-lg shadow-sm border p-3 flex items-center gap-3">
              <input value={folderId} onChange={(e) => setFolderId(e.target.value)}
                placeholder="Folder ID" className="flex-1 px-3 py-1.5 border border-gray-300 rounded text-sm" />
              <button onClick={() => listFolder(folderId)} disabled={loading}
                className="px-3 py-1.5 bg-primary text-white rounded text-sm disabled:opacity-50">
                {loading ? "..." : "Go"}
              </button>
              <button onClick={() => window.location.href = "/api/oauth/login"}
                className="px-3 py-1.5 border border-gray-300 rounded text-sm hover:bg-gray-50">
                Re-auth
              </button>
              {selected.size > 0 && (
                <button onClick={handleDownloadSelected}
                  className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700">
                  Download ({selected.size})
                </button>
              )}
            </div>

            {/* Breadcrumb */}
            <div className="flex items-center gap-1 text-sm text-gray-500 overflow-x-auto">
              {folderPath.map((p, i) => (
                <span key={p.id} className="flex items-center gap-1 whitespace-nowrap">
                  {i > 0 && <span>/</span>}
                  <button onClick={() => navigateTo(p.id, p.name)}
                    className={i === folderPath.length - 1 ? "text-gray-900 font-medium" : "text-primary hover:underline"}>
                    {p.name}
                  </button>
                </span>
              ))}
            </div>

            {/* File Table */}
            <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
              {files.length === 0 && !loading ? (
                <p className="p-8 text-center text-gray-400">Empty folder</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b">
                    <tr className="text-left text-gray-500">
                      <th className="px-4 py-2 w-8">
                        <input type="checkbox" checked={selected.size === files.length && files.length > 0}
                          onChange={selectAll} className="rounded" />
                      </th>
                      <th className="px-4 py-2">Name</th>
                      <th className="px-4 py-2">Type</th>
                      <th className="px-4 py-2">Size</th>
                      <th className="px-4 py-2">Modified</th>
                      <th className="px-4 py-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {folders.map((f) => (
                      <tr key={f.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2"><input type="checkbox" checked={selected.has(f.id)} onChange={() => toggleSelect(f.id)} className="rounded" /></td>
                        <td className="px-4 py-2">
                          <button onClick={() => navigateTo(f.id, f.name)} className="text-primary hover:underline font-medium flex items-center gap-2">
                            <span className="text-yellow-500">Folder</span>
                            {f.name}
                          </button>
                        </td>
                        <td className="px-4 py-2 text-xs text-gray-400">Folder</td>
                        <td className="px-4 py-2 text-xs text-gray-400">-</td>
                        <td className="px-4 py-2 text-xs text-gray-400">{f.modifiedTime ? new Date(f.modifiedTime).toLocaleDateString() : "-"}</td>
                        <td className="px-4 py-2">
                          <button onClick={() => navigateTo(f.id, f.name)} className="text-xs text-primary hover:underline">Open</button>
                        </td>
                      </tr>
                    ))}
                    {fileItems.map((f) => (
                      <tr key={f.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2"><input type="checkbox" checked={selected.has(f.id)} onChange={() => toggleSelect(f.id)} className="rounded" /></td>
                        <td className="px-4 py-2 font-mono text-xs">{f.name}</td>
                        <td className="px-4 py-2 text-xs text-gray-400">{f.mimeType?.split(".").pop() || f.mimeType?.split("/").pop()}</td>
                        <td className="px-4 py-2 text-xs">{f.size_mb > 0 ? `${f.size_mb} MB` : "-"}</td>
                        <td className="px-4 py-2 text-xs text-gray-400">{f.modifiedTime ? new Date(f.modifiedTime).toLocaleDateString() : "-"}</td>
                        <td className="px-4 py-2 flex gap-2">
                          <button onClick={() => handleDownload(f)} className="text-xs text-green-600 hover:underline">Download</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Download Progress Panel */}
            {downloads.length > 0 && (
              <div className="bg-white rounded-lg shadow-sm border p-4">
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Downloads</h3>
                  <button onClick={() => setDownloads([])} className="text-xs text-gray-400 hover:text-gray-600">Clear</button>
                </div>
                <div className="space-y-2">
                  {downloads.map((d, i) => (
                    <div key={`${d.id}-${i}`} className="flex items-center gap-3 text-sm">
                      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        d.status === "finished" ? "bg-green-500" :
                        d.status === "error" || d.status === "failed" ? "bg-red-500" :
                        d.status === "running" ? "bg-blue-500 animate-pulse" :
                        "bg-yellow-500"
                      }`} />
                      <span className="font-mono text-xs truncate w-48">{d.fileName}</span>
                      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full transition-all duration-300 ${
                          d.status === "finished" ? "bg-green-500" :
                          d.status === "error" || d.status === "failed" ? "bg-red-500" :
                          "bg-blue-500"
                        }`} style={{ width: `${Math.min(d.progress, 100)}%` }} />
                      </div>
                      <span className="text-xs text-gray-500 w-12 text-right">{d.progress}%</span>
                      <span className="text-xs text-gray-400 truncate w-24">{d.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {configured === null && <p className="text-center text-gray-400 p-8">Loading...</p>}
      </main>
    </div>
  );
}
