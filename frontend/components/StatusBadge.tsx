const statusColors: Record<string, string> = {
  queued: "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200",
  running: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/50 dark:text-cyan-200",
  finished: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200",
  done: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-200",
  error: "bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-200",
  submitted: "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200",
  pending: "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-300",
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex whitespace-nowrap rounded px-2 py-0.5 text-xs font-medium ${
        statusColors[status] || "bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300"
      }`}
    >
      {status}
    </span>
  );
}
