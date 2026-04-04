"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasAdmin, setHasAdmin] = useState<boolean | null>(null);

  useEffect(() => {
    fetch("/api/auth/status")
      .then((r) => r.json())
      .then((d) => {
        setHasAdmin(!d.needsSetup);
      })
      .catch(() => setHasAdmin(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 4) {
      setError("Password must be at least 4 characters");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Registration failed");
        return;
      }
      router.push("/dashboard");
      router.refresh();
    } catch {
      setError("Connection error");
    }
    setLoading(false);
  }

  if (hasAdmin === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-50 px-4 dark:bg-stone-950">
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  if (hasAdmin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-50 px-4 dark:bg-stone-950">
        <div className="w-full max-w-sm rounded-lg border border-stone-200 bg-white p-8 shadow-md dark:border-stone-700 dark:bg-stone-900 text-center space-y-4">
          <h1 className="text-2xl font-bold">Admin Already Exists</h1>
          <p className="text-sm text-stone-500 dark:text-stone-400">An admin account has already been created.</p>
          <a href="/login" className="inline-block px-6 py-2 bg-emerald-700 text-white rounded-md hover:bg-emerald-800 text-sm font-medium">
            Go to Login
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50 px-4 dark:bg-stone-950">
      <div className="w-full max-w-sm rounded-lg border border-stone-200 bg-white p-8 shadow-md dark:border-stone-700 dark:bg-stone-900">
        <h1 className="text-2xl font-bold text-center mb-2">Create Admin Account</h1>
        <p className="text-center mb-6 text-stone-500 dark:text-stone-400">Set up your admin credentials</p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <label className="block mb-4">
            <span className="text-sm font-medium text-stone-700 dark:text-stone-200">Username</span>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              className="mt-1 block w-full rounded-md border border-stone-300 bg-white px-3 py-2 shadow-sm focus:border-emerald-700 focus:outline-none focus:ring-emerald-700 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-100"
            />
          </label>

          <label className="block mb-4">
            <span className="text-sm font-medium text-stone-700 dark:text-stone-200">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={4}
              className="mt-1 block w-full rounded-md border border-stone-300 bg-white px-3 py-2 shadow-sm focus:border-emerald-700 focus:outline-none focus:ring-emerald-700 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-100"
            />
          </label>

          <label className="block mb-6">
            <span className="text-sm font-medium text-stone-700 dark:text-stone-200">Confirm Password</span>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              className="mt-1 block w-full rounded-md border border-stone-300 bg-white px-3 py-2 shadow-sm focus:border-emerald-700 focus:outline-none focus:ring-emerald-700 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-100"
            />
          </label>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-emerald-700 px-4 py-2 font-medium text-white hover:bg-emerald-800 disabled:opacity-50"
          >
            {loading ? "Creating..." : "Create Account"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-gray-500">
          Already have an account? <a href="/login" className="text-emerald-700 hover:underline dark:text-emerald-400">Login</a>
        </p>
      </div>
    </div>
  );
}
