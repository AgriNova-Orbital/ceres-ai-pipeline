"use client";

import { useCallback, useState } from "react";

interface UseApiSubmitOptions {
  onSuccess?: (data: Record<string, unknown>) => void;
  successMessage?: string;
}

interface UseApiSubmitReturn {
  loading: boolean;
  result: string;
  error: string;
  jobId: string | null;
  submit: (
    url: string,
    body?: Record<string, unknown> | FormData
  ) => Promise<void>;
  clearResult: () => void;
  clearError: () => void;
}

export function useApiSubmit(
  options?: UseApiSubmitOptions
): UseApiSubmitReturn {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);

  const submit = useCallback(
    async (
      url: string,
      body?: Record<string, unknown> | FormData
    ) => {
      setLoading(true);
      setResult("");
      setError("");
      setJobId(null);

      try {
        const isFormData = body instanceof FormData;
        const res = await fetch(url, {
          method: "POST",
          headers: isFormData
            ? undefined
            : { "Content-Type": "application/json" },
          body: isFormData ? body : JSON.stringify(body),
        });
        const data = await res.json();

        if (res.ok) {
          const id = data.job_id || null;
          setJobId(id);
          setResult(
            options?.successMessage ||
              (id ? `Job queued: ${id}` : "Operation completed")
          );
          options?.onSuccess?.(data);
        } else {
          setError(data.error || "Request failed");
        }
      } catch {
        setError("Connection error. Please check if the server is running.");
      } finally {
        setLoading(false);
      }
    },
    [options]
  );

  return {
    loading,
    result,
    error,
    jobId,
    submit,
    clearResult: () => setResult(""),
    clearError: () => setError(""),
  };
}
