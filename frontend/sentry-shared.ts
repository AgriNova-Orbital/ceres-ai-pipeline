const REDACTED = "[Filtered]";

const SENSITIVE_KEY_MARKERS = [
  "authorization",
  "cookie",
  "password",
  "passwd",
  "secret",
  "token",
  "api_key",
  "apikey",
  "x_api_key",
  "dsn",
  "credential",
  "client_secret",
  "refresh_token",
  "access_token",
  "clerk",
  "new_relic",
  "sentry_auth_token",
];

const BEARER_PATTERN = /\b(authorization\s*:\s*bearer\s+)([^\s,;]+)/gi;
const COOKIE_PATTERN = /\b(cookie\s*:\s*)([^\n]+)/gi;
const ASSIGNMENT_PATTERN =
  /\b((?:access|refresh)[_-]?token|client[_-]?secret|api[_-]?key|sentry[_-]?dsn|sentry[_-]?auth[_-]?token|new[_-]?relic[_-]?license[_-]?key|clerk[_-]?secret[_-]?key|password|passwd|secret|token)\b(\s*[:=]\s*)([^\s,;&]+)/gi;

export function scrubSentryData<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item) => scrubSentryData(item)) as T;
  }
  if (typeof value === "string") {
    return scrubSensitiveString(value) as T;
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, entry]) => [
        key,
        isSensitiveKey(key) ? REDACTED : scrubSentryData(entry),
      ])
    ) as T;
  }
  return value;
}

export function scrubSentryEvent<T>(event: T): T {
  return scrubSentryData(event);
}

export function scrubSentryLog<T>(log: T): T {
  return scrubSentryData(log);
}

function isSensitiveKey(key: string): boolean {
  const normalized = key.toLowerCase().replaceAll("-", "_");
  return SENSITIVE_KEY_MARKERS.some((marker) => normalized.includes(marker));
}

function scrubSensitiveString(value: string): string {
  return value
    .replace(BEARER_PATTERN, `$1${REDACTED}`)
    .replace(COOKIE_PATTERN, `$1${REDACTED}`)
    .replace(ASSIGNMENT_PATTERN, `$1$2${REDACTED}`);
}
