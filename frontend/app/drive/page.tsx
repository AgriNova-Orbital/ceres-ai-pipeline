"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";

interface DriveFile {
  id: string;
  name: string;
  size_mb: number;
  mimeType: string;
}

export default function DrivePage() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [error, setError] = useState("");
  const [folderId, setFolderId] = useState("root");
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadMsg, setUploadMsg] = useState("");

  async function checkStatus() {
    try {
      const res = await fetch("/api/oauth/status");
      const data = await res.json();
      setConfigured(data.configured);
      if (data.configured) {
        listFolder("root");
      }
    } catch {
      setConfigured(false);
    }
  }

  async function listFolder(id: string) {
    setLoading(true);
    try {
      const res = await fetch(`/api/drive/list?id=${id}`);
      if (res.ok) {
        const data = await res.json();
        setFiles(data.files || []);
        setError("");
      } else {
        const data = await res.json();
        setError(data.error || "Failed to list files");
      }
    } catch {
      setError("Connection error");
    }
    setLoading(false);
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!uploadFile) return;
    setLoading(true);
    try {
      const form = new FormData();
      form.append("file", uploadFile);
      form.append("redirect_base_url", typeof window !== "undefined" ? window.location.origin : "");
      const res = await fetch("/api/oauth/upload-secret", { method: "POST", body: form });
      const data = await res.json();
      if (res.ok) {
        setUploadMsg("Uploaded! Now click 'Connect to Google Drive' below.");
        setConfigured(true);
      } else {
        setError(data.error || "Upload failed");
      }
    } catch {
      setError("Connection error");
    }
    setLoading(false);
  }

  function handleConnect() {
    window.location.href = "/api/oauth/login";
  }

  useEffect(() => { checkStatus(); }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-8 py-4 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-primary hover:underline">&larr; Home</Link>
          <h1 className="text-xl font-bold">Google Drive</h1>
        </div>
        <LogoutButton />
      </header>

      <main className="max-w-5xl mx-auto p-6 space-y-6">
        {error && <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm">{error}</div>}
        {uploadMsg && <div className="p-3 bg-green-50 border border-green-200 text-green-700 rounded text-sm">{uploadMsg}</div>}

        {/* Step 1: Upload client_secret.json (if not configured) */}
        {configured === false && (
          <div className="bg-white rounded-lg shadow-sm border p-6 space-y-4">
            <h2 className="text-lg font-semibold">Step 1: Configure OAuth</h2>
            <form onSubmit={handleUpload} className="space-y-4">
              <label className="block">
                <span className="text-sm font-medium text-gray-700">client_secret.json</span>
                <input
                  type="file"
                  accept=".json"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="mt-1 block w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:bg-primary file:text-white"
                />
              </label>
              <button type="submit" disabled={loading || !uploadFile}
                className="px-4 py-2 bg-primary text-white rounded-md text-sm hover:bg-primary-dark disabled:opacity-50">
                {loading ? "Uploading..." : "Upload"}
              </button>
            </form>
          </div>
        )}

        {/* Step 2: Connect (if configured but not browsing) */}
        {configured && files.length === 0 && !loading && (
          <div className="bg-white rounded-lg shadow-sm border p-8 text-center space-y-4">
            <h2 className="text-xl font-semibold">Connect to Google Drive</h2>
            <p className="text-gray-500">Authorize this app to access your Google Drive files.</p>
            <button onClick={handleConnect}
              className="px-6 py-3 bg-primary text-white rounded-md hover:bg-primary-dark font-medium mx-auto">
              Connect to Google Drive
            </button>
          </div>
        )}

        {/* Step 3: Browse files (connected) */}
        {configured && (
          <>
            <div className="bg-white rounded-lg shadow-sm border p-4 flex gap-2">
              <input
                value={folderId}
                onChange={(e) => setFolderId(e.target.value)}
                placeholder="Folder ID or 'root'"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
              <button onClick={() => listFolder(folderId)} disabled={loading}
                className="px-4 py-2 bg-primary text-white rounded-md text-sm hover:bg-primary-dark disabled:opacity-50">
                {loading ? "Loading..." : "Browse"}
              </button>
              <button onClick={handleConnect}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50">
                Re-authorize
              </button>
            </div>

            <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
              {files.length === 0 && !loading ? (
                <p className="p-8 text-center text-gray-400">Enter a folder ID and click Browse</p>
              ) : files.length === 0 ? (
                <p className="p-8 text-center text-gray-400">Loading...</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b">
                    <tr className="text-left text-gray-500">
                      <th className="px-4 py-3">Name</th>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Size</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {files.map((f) => (
                      <tr key={f.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2">
                          {f.mimeType === "application/vnd.google-apps.folder" ? (
                            <button onClick={() => { setFolderId(f.id); listFolder(f.id); }}
                              className="text-primary hover:underline font-mono text-xs">
                              {f.name}
                            </button>
                          ) : (
                            <span className="font-mono text-xs">{f.name}</span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-xs text-gray-400">
                          {f.mimeType?.split(".").pop() || f.mimeType?.split("/").pop()}
                        </td>
                        <td className="px-4 py-2 text-xs">{f.size_mb > 0 ? `${f.size_mb} MB` : "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}

        {/* Checking */}
        {configured === null && (
          <p className="text-center text-gray-400 p-8">Loading...</p>
        )}
      </main>
    </div>
  );
}
