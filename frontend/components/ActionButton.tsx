"use client";

import { useState } from "react";

export default function ActionButton({
  label,
  endpoint,
  method = "POST",
  body,
}: {
  label: string;
  endpoint: string;
  method?: string;
  body?: Record<string, unknown>;
}) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function handleClick() {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(endpoint, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await res.json();
      if (res.ok) {
        setResult(`Queued: ${data.job_id || JSON.stringify(data)}`);
      } else {
        setResult(`Error: ${data.error || res.statusText}`);
      }
    } catch (e: unknown) {
      setResult(`Error: ${e instanceof Error ? e.message : "Connection failed"}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mb-3">
      <button
        onClick={handleClick}
        disabled={loading}
        className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary-dark disabled:opacity-50 text-sm"
      >
        {loading ? "Running..." : label}
      </button>
      {result && (
        <span className={`ml-3 text-sm ${result.startsWith("Error") ? "text-red-600" : "text-green-600"}`}>
          {result}
        </span>
      )}
    </div>
  );
}
