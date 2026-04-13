interface SubmitButtonProps {
  loading: boolean;
  onClick: () => void;
  label: string;
  loadingLabel?: string;
  disabled?: boolean;
  variant?: "primary" | "danger";
}

export default function SubmitButton({
  loading,
  onClick,
  label,
  loadingLabel,
  disabled,
  variant = "primary",
}: SubmitButtonProps) {
  const styles = {
    primary: "bg-emerald-700 text-white hover:bg-emerald-800 disabled:hover:bg-emerald-700",
    danger: "bg-red-600 text-white hover:bg-red-700 disabled:hover:bg-red-600",
  };

  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className={`rounded-md px-6 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]}`}
    >
      {loading ? (
        <span className="flex items-center gap-2">
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {loadingLabel || "Submitting…"}
        </span>
      ) : (
        label
      )}
    </button>
  );
}
