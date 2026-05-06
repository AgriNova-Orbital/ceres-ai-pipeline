import * as Sentry from "@sentry/nextjs";
import { consoleLoggingIntegration } from "@sentry/core";
import { scrubSentryEvent, scrubSentryLog } from "./sentry-shared";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
const enableLogs = process.env.NEXT_PUBLIC_SENTRY_ENABLE_LOGS !== "false";

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development",
    release: process.env.NEXT_PUBLIC_SENTRY_RELEASE,
    tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE || "0"),
    enableLogs,
    beforeSend: scrubSentryEvent,
    beforeSendLog: scrubSentryLog,
    integrations: [
      consoleLoggingIntegration({ levels: ["debug", "info", "log", "warn", "error"] }),
    ],
  });
}

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
