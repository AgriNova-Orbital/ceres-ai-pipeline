import Link from "next/link";
import { useEffect, useState } from "react";

interface FeedbackMessageProps {
  message: string;
  type?: "success" | "error" | "info";
  jobId?: string;
  autoClearMs?: number;
  onClear?: () => void;
}

export default function FeedbackMessage({
  message,
  type = "info",
  jobId,
  autoClearMs = 8000,
  onClear,
}: FeedbackMessageProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    setVisible(true);
    if (autoClearMs && type === "success") {
      const timer = setTimeout(() => {
        setVisible(false);
        onClear?.();
      }, autoClearMs);
      return () => clearTimeout(timer);
    }
  }, [message, autoClearMs, type, onClear]);

  if (!visible || !message) return null;

  const styles = {
    success: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200",
    error: "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-200",
    info: "border-cyan-200 bg-cyan-50 text-cyan-700 dark:border-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-200",
  };

  const icons = { success: "✓", error: "✗", info: "ℹ" };

  return (
    <div className={`flex items-start gap-3 rounded border p-3 text-sm ${styles[type]}`}>
      <span className="mt-px font-bold">{icons[type]}</span>
      <div className="flex-1">
        <p>{message}</p>
        {jobId && (
          <Link href="/jobs" className="mt-1 inline-block text-xs underline hover:no-underline">
            View job status →
          </Link>
        )}
      </div>
      <button
        onClick={() => {
          setVisible(false);
          onClear?.();
        }}
        className="text-current opacity-50 hover:opacity-100"
      >
        ×
      </button>
    </div>
  );
}
