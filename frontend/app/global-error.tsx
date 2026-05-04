"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-6 text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-amber-500">
            Ceres AI Pipeline
          </p>
          <h1 className="mt-4 text-3xl font-semibold text-slate-950">
            Something went wrong
          </h1>
          <p className="mt-3 text-sm text-slate-600">
            The error was reported. Retry this page or check the job/API logs if
            it persists.
          </p>
          <button
            className="mx-auto mt-6 rounded-full bg-slate-950 px-5 py-2 text-sm font-semibold text-white"
            onClick={reset}
            type="button"
          >
            Retry
          </button>
        </main>
      </body>
    </html>
  );
}
