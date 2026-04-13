"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import LogoutButton from "@/components/LogoutButton";
import ThemeSwitcher from "@/components/ThemeSwitcher";
import LanguageSwitcher from "@/components/LanguageSwitcher";

export default function SettingsPage() {
  const [oauthConfigured, setOauthConfigured] = useState<boolean | null>(null);
  const [redirectBase, setRedirectBase] = useState("");
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

  useEffect(() => { checkStatus(); }, []);

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
        setMessage("client_secret.json uploaded! You can now connect to Google Drive.");
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
    if (!confirm("Remove Google Drive connection?")) return;
    await fetch("/api/oauth/disconnect", { method: "POST" });
    setOauthConfigured(false);
    setMessage("Google Drive disconnected");
  }

  return (
    <div className="min-h-screen bg-stone-50 dark:bg-stone-950">
      <header className="border-b bg-white dark:border-stone-800 dark:bg-stone-900 px-4 sm:px-8 py-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center gap-4">
          <Link href="/dashboard" className="text-emerald-700 hover:underline dark:text-emerald-400">&larr; Home</Link>
          <h1 className="text-xl font-bold">Settings</h1>
        </div>
        <div className="flex items-center gap-2">
          <ThemeSwitcher />
          <LanguageSwitcher />
          <LogoutButton />
        </div>
      </header>

      <main className="mx-auto max-w-2xl space-y-6 p-6">
        {message && <div className="p-3 bg-green-50 border border-green-200 text-green-700 rounded text-sm">{message}</div>}
        {error && <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm">{error}</div>}

        {/* Google Drive Connection */}
        <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-700 dark:bg-stone-900">
          <h2 className="text-lg font-semibold mb-4">Google Drive Connection</h2>
          {oauthConfigured === null ? (
            <p className="text-stone-400">Checking...</p>
          ) : oauthConfigured ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 bg-green-500 rounded-full" />
                <span className="text-green-700 font-medium">Connected</span>
              </div>
              <p className="text-sm text-stone-500 dark:text-stone-400">Google Drive is configured and ready to use.</p>
              <div className="flex gap-2">
                <Link href="/drive"
                  className="px-4 py-2 rounded-md bg-emerald-700 px-4 py-2 text-sm text-white hover:bg-emerald-800">
                  Browse Drive
                </Link>
                <button onClick={handleDisconnect}
                  className="px-4 py-2 rounded-md border border-red-300 px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:border-red-700 dark:text-red-400 dark:hover:bg-red-950/40">
                  Disconnect
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 bg-gray-300 rounded-full" />
                <span className="text-stone-500 dark:text-stone-400">Not connected</span>
              </div>
              <p className="text-sm text-stone-500 dark:text-stone-400">
                Upload your Google OAuth <code className="bg-stone-100 px-1 rounded dark:bg-stone-800">client_secret.json</code> to enable Google Drive access.
              </p>
            </div>
          )}
        </div>

        {/* Upload Form */}
        <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-700 dark:bg-stone-900">
          <h2 className="text-lg font-semibold mb-4">Configure Google Drive</h2>
          <form onSubmit={handleUpload} className="space-y-4">
            <label className="block">
              <span className="text-sm font-medium text-stone-700 dark:text-stone-200">Redirect Base URL</span>
              <input
                value={redirectBase}
                onChange={(e) => setRedirectBase(e.target.value)}
                placeholder="https://your-domain.com"
                className="mt-1 block w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800 dark:text-stone-100"
              />
              <p className="text-xs text-stone-400 mt-1">
                Must match the Authorized redirect URI in Google Cloud Console
              </p>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-stone-700 dark:text-stone-200">client_secret.json</span>
              <input
                type="file"
                accept=".json"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                className="mt-1 block w-full text-sm text-stone-500 dark:text-stone-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:bg-primary file:text-white hover:file:bg-primary-dark"
              />
            </label>
            <button type="submit" disabled={loading}
              className="rounded-md bg-emerald-700 px-6 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50">
              {loading ? "Uploading..." : "Upload & Connect"}
            </button>
          </form>
        </div>

        {/* Instructions */}
        <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-700 dark:bg-stone-900">
          <h2 className="text-lg font-semibold mb-4">Setup Instructions</h2>
          <ol className="list-decimal list-inside space-y-2 text-sm text-gray-600">
            <li>Go to <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener" className="text-emerald-700 hover:underline dark:text-emerald-400">Google Cloud Console → Credentials</a></li>
            <li>Create an OAuth 2.0 Client ID (type: <strong>Web application</strong>)</li>
            <li>Add <code className="bg-stone-100 px-1 rounded dark:bg-stone-800">{redirectBase || "your-domain"}/api/oauth/callback</code> as <strong>Authorized redirect URI</strong></li>
            <li>Enable the <strong>Google Drive API</strong> in your project</li>
            <li>Download the JSON file and upload it here</li>
            <li>Click <strong>Connect to Google Drive</strong> and authorize access</li>
          </ol>
        </div>
      </main>
    </div>
  );
}
