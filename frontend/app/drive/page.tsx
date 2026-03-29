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
  const [connected, setConnected] = useState<boolean | null>(null);
  const [error, setError] = useState("");
  const [folderId, setFolderId] = useState("root");
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [loading, setLoading] = useState(false);

  async function checkStatus() {
    try {
      const res = await fetch("/api/oauth/status");
      const data = await res.json();
      setConnected(data.configured);
      if (data.configured) {
        listFolder("root");
      }
    } catch {
      setConnected(false);
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
        {/* Not connected */}
        {connected === false && (
          <div className="bg-white rounded-lg shadow-sm border p-8 text-center space-y-4">
            <div className="text-4xl">Google Drive</div>
            <p className="text-gray-500">Connect your Google account to browse and download files.</p>
            <button onClick={handleConnect}
              className="px-6 py-3 bg-primary text-white rounded-md hover:bg-primary-dark font-medium flex items-center gap-2 mx-auto">
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
              </svg>
              Connect to Google Drive
            </button>
            <p className="text-xs text-gray-400">
              Need to configure first? Go to <Link href="/settings" className="text-primary hover:underline">Settings</Link>
            </p>
          </div>
        )}

        {/* Connected - File Browser */}
        {connected && (
          <>
            {error && <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm">{error}</div>}

            <div className="bg-white rounded-lg shadow-sm border p-4 flex gap-2">
              <input
                value={folderId}
                onChange={(e) => setFolderId(e.target.value)}
                placeholder="Google Drive Folder ID (or 'root')"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
              <button onClick={() => listFolder(folderId)} disabled={loading}
                className="px-4 py-2 bg-primary text-white rounded-md text-sm hover:bg-primary-dark disabled:opacity-50">
                {loading ? "Loading..." : "Browse"}
              </button>
            </div>

            <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
              {files.length === 0 ? (
                <p className="p-8 text-center text-gray-400">{loading ? "Loading..." : "No files in this folder"}</p>
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
        {connected === null && (
          <p className="text-center text-gray-400 p-8">Checking connection...</p>
        )}
      </main>
    </div>
  );
}
