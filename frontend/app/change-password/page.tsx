import Link from "next/link";

export default function ChangePasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-stone-50 px-4 text-stone-900 dark:bg-stone-950 dark:text-stone-100">
      <main className="w-full max-w-md rounded-lg border border-stone-200 bg-white p-8 text-center shadow-md dark:border-stone-700 dark:bg-stone-900">
        <h1 className="text-2xl font-bold">Password Managed By Clerk</h1>
        <p className="mt-3 text-sm text-stone-500 dark:text-stone-400">
          Ceres AI now uses Clerk for account passwords. Use the account menu after signing in to manage your password.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Link href="/dashboard" className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800">
            Back to dashboard
          </Link>
          <Link href="/login" className="rounded-md border border-stone-300 px-4 py-2 text-sm font-medium hover:bg-stone-100 dark:border-stone-600 dark:hover:bg-stone-800">
            Sign in
          </Link>
        </div>
      </main>
    </div>
  );
}
