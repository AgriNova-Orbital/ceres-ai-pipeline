"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";

export default function SettingsPage() {
  const [oauthConfigured, setOauthConfigured] = useState<boolean | null>(null);
  const [redirectBase, setRedirectBase] = useState("");
  const [mounted, setMounted] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function checkStatus() {
    try {
      const res = await fetch("/api/oauth/status");
      const data = await res.json();
      setOauthConfigured(data.configured);
      setRedirectBase(data.redirect_base || (typeof window !== "undefined" ? window.location.origin : ""));
    } catch {
      setOauthConfigured(false);
    }
  }

  useEffect(() => {
    setMounted(true);
    checkStatus();
  }, []);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!uploadFile) { setError("Select a file"); return; }
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const form = new FormData();
      form.append("file", uploadFile);
      form.append("redirect_base_url", redirectBase);
      const res = await fetch("/api/oauth/upload-secret", { method: "POST", body: form });
      const data = await res.json();
      if (res.ok) {
        setMessage("OAuth client secret uploaded successfully!");
        setOauthConfigured(true);
        setUploadFile(null);
      } else {
        setError(data.error || "Upload failed");
      }
    } catch {
      setError("Connection error");
    }
    setLoading(false);
  }

  async function handleDisconnect() {
    if (!confirm("Remove OAuth configuration?")) return;
    await fetch("/api/oauth/disconnect", { method: "POST" });
    setOauthConfigured(false);
    setMessage("OAuth disconnected");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-8 py-4 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-primary hover:underline">&larr; Home</Link>
          <h1 className="text-xl font-bold">Settings</h1>
        </div>
        <LogoutButton />
      </header>

      <main className="max-w-2xl mx-auto p-6 space-y-6">
        {message && <div className="p-3 bg-green-50 border border-green-200 text-green-700 rounded text-sm">{message}</div>}
        {error && <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm">{error}</div>}

        {/* OAuth Status */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="text-lg font-semibold mb-4">Google OAuth</h2>
          {oauthConfigured === null ? (
            <p className="text-gray-400">Checking...</p>
          ) : oauthConfigured ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 bg-green-500 rounded-full" />
                <span className="text-green-700 font-medium">Configured</span>
              </div>
              <button onClick={handleDisconnect}
                className="px-4 py-2 border border-red-300 text-red-600 rounded-md text-sm hover:bg-red-50">
                Disconnect
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 bg-gray-300 rounded-full" />
                <span className="text-gray-500">Not configured</span>
              </div>
              <p className="text-sm text-gray-500">
                Upload your Google OAuth <code className="bg-gray-100 px-1 rounded">client_secret.json</code> to enable Google Sign-In.
              </p>
            </div>
          )}
        </div>

        {/* Upload Form */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="text-lg font-semibold mb-4">Upload OAuth Client Secret</h2>
          <form onSubmit={handleUpload} className="space-y-4">
            <label className="block">
              <span className="text-sm font-medium text-gray-700">Redirect Base URL</span>
              <input
                value={redirectBase}
                onChange={(e) => setRedirectBase(e.target.value)}
                placeholder="https://your-domain.com"
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
              <p className="text-xs text-gray-400 mt-1">
                Must match the Authorized redirect URI in Google Cloud Console (e.g., https://your-domain.com/api/oauth/callback)
              </p>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700">client_secret.json</span>
              <input
                type="file"
                accept=".json"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                className="mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:bg-primary file:text-white hover:file:bg-primary-dark"
              />
            </label>
            <button type="submit" disabled={loading}
              className="px-6 py-2 bg-primary text-white rounded-md hover:bg-primary-dark disabled:opacity-50 text-sm font-medium">
              {loading ? "Uploading..." : "Upload & Configure"}
            </button>
          </form>
        </div>

        {/* Instructions */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="text-lg font-semibold mb-4">How to get client_secret.json</h2>
          <ol className="list-decimal list-inside space-y-2 text-sm text-gray-600">
            <li>Go to <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener" className="text-primary hover:underline">Google Cloud Console → Credentials</a></li>
            <li>Create an OAuth 2.0 Client ID (type: Web application)</li>
            <li>Add <code className="bg-gray-100 px-1 rounded">{redirectBase || "your-domain"}/api/oauth/callback</code> as Authorized redirect URI</li>
            <li>Download the JSON file and upload it here</li>
          </ol>
        </div>
      </main>
    </div>
  );
}
