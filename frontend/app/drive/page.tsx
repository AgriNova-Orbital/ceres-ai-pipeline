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
  const [folderId, setFolderId] = useState("");
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [loading, setLoading] = useState(false);

  async function checkStatus() {
    try {
      const res = await fetch("/api/drive/list?id=root");
      if (res.ok) {
        setConnected(true);
        const data = await res.json();
        setFiles(data.files || []);
      } else {
        const data = await res.json();
        setConnected(false);
        setError(data.error || "Not connected");
      }
    } catch {
      setConnected(false);
      setError("Cannot reach API");
    }
  }

  async function listFolder() {
    if (!folderId) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/drive/list?id=${folderId}`);
      const data = await res.json();
      setFiles(data.files || []);
    } catch { /* ignore */ }
    setLoading(false);
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

      <main className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Status */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="text-lg font-semibold mb-4">Connection Status</h2>
          {connected === null ? (
            <p className="text-gray-400">Checking...</p>
          ) : connected ? (
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 bg-green-500 rounded-full" />
              <span className="text-green-700 font-medium">Connected</span>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 bg-red-500 rounded-full" />
                <span className="text-red-700 font-medium">Not Connected</span>
              </div>
              <p className="text-sm text-gray-500">{error}</p>
              <div className="bg-yellow-50 border border-yellow-200 rounded p-4 text-sm text-yellow-800">
                <p className="font-medium mb-1">Google OAuth Required</p>
                <p>Drive integration requires Google OAuth, which is currently in WIP status.</p>
                <p className="mt-2">To enable: upload a <code className="bg-yellow-100 px-1 rounded">client_secret.json</code> and configure OAuth.</p>
              </div>
            </div>
          )}
        </div>

        {/* File Browser (only if connected) */}
        {connected && (
          <div className="bg-white rounded-lg shadow-sm border p-6 space-y-4">
            <h2 className="text-lg font-semibold">Browse Files</h2>
            <div className="flex gap-2">
              <input
                value={folderId}
                onChange={(e) => setFolderId(e.target.value)}
                placeholder="Google Drive Folder ID"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
              <button onClick={listFolder} disabled={loading}
                className="px-4 py-2 bg-primary text-white rounded-md text-sm hover:bg-primary-dark disabled:opacity-50">
                {loading ? "Loading..." : "List"}
              </button>
            </div>

            {files.length > 0 && (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr className="text-left text-gray-500">
                    <th className="px-4 py-2">Name</th>
                    <th className="px-4 py-2">Type</th>
                    <th className="px-4 py-2">Size</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {files.map((f) => (
                    <tr key={f.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-xs">{f.name}</td>
                      <td className="px-4 py-2 text-xs text-gray-400">{f.mimeType?.split(".").pop()}</td>
                      <td className="px-4 py-2 text-xs">{f.size_mb} MB</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
