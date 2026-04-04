"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function ChangePasswordForm() {
  const router = useRouter();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          new_password: newPassword,
          confirm_password: confirmPassword,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Failed to change password");
        return;
      }

      router.push("/dashboard");
      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50 px-4 dark:bg-stone-950">
      <div className="w-full max-w-sm rounded-lg border border-stone-200 bg-white p-8 shadow-md dark:border-stone-700 dark:bg-stone-900">
        <h1 className="text-2xl font-bold text-center mb-2">Change Password</h1>
        <p className="text-center mb-6 text-stone-500 dark:text-stone-400">
          Please set a new password before continuing.
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <label className="block mb-4">
            <span className="text-sm font-medium text-stone-700 dark:text-stone-200">New Password</span>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={4}
              autoFocus
              className="mt-1 block w-full rounded-md border border-stone-300 bg-white px-3 py-2 shadow-sm focus:border-emerald-700 focus:outline-none focus:ring-emerald-700 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-100"
            />
          </label>

          <label className="block mb-6">
            <span className="text-sm font-medium text-stone-700 dark:text-stone-200">Confirm Password</span>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="mt-1 block w-full rounded-md border border-stone-300 bg-white px-3 py-2 shadow-sm focus:border-emerald-700 focus:outline-none focus:ring-emerald-700 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-100"
            />
          </label>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-emerald-700 px-4 py-2 font-medium text-white hover:bg-emerald-800 disabled:opacity-50"
          >
            {loading ? "Updating..." : "Update Password"}
          </button>
        </form>
      </div>
    </div>
  );
}
