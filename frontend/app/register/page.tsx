import { SignUp } from "@clerk/nextjs";

export default function RegisterPage() {
  const clerkPublishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

  if (!clerkPublishableKey) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-stone-50 px-4 py-16 dark:bg-stone-950">
        <div className="max-w-md rounded-lg border border-stone-200 bg-white p-8 text-center shadow-md dark:border-stone-700 dark:bg-stone-900">
          <h1 className="text-2xl font-bold">Clerk is not configured</h1>
          <p className="mt-3 text-sm text-stone-500 dark:text-stone-400">
            Set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY to enable sign up.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-stone-50 px-4 py-16 dark:bg-stone-950">
      <SignUp routing="path" path="/register" signInUrl="/login" />
    </main>
  );
}
