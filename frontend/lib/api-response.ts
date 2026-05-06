export type ApiResponseData = Record<string, unknown>;

export type ApiResponseResult<T extends ApiResponseData = ApiResponseData> =
  | { ok: true; data: T; error: "" }
  | { ok: false; data: ApiResponseData; error: string };

const SESSION_EXPIRED_MESSAGE = "Your sign-in session expired. Please sign in again.";
const FORBIDDEN_MESSAGE = "You do not have permission to access this resource.";
const AUTH_SERVICE_UNAVAILABLE_MESSAGE =
  "Authentication service is temporarily unavailable. Please retry in a moment.";

export async function readApiResponse<T extends ApiResponseData = ApiResponseData>(
  response: Response,
  fallback = "Request failed"
): Promise<ApiResponseResult<T>> {
  const data = await readJsonObject(response);
  if (response.ok) {
    return { ok: true, data: data as T, error: "" };
  }
  return { ok: false, data, error: apiErrorMessage(response.status, data, fallback) };
}

async function readJsonObject(response: Response): Promise<ApiResponseData> {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.toLowerCase().includes("application/json")) {
    return {};
  }
  try {
    const data = await response.json();
    return isRecord(data) ? data : {};
  } catch {
    return {};
  }
}

function apiErrorMessage(status: number, data: ApiResponseData, fallback: string): string {
  if (status === 401) {
    return SESSION_EXPIRED_MESSAGE;
  }
  if (status === 403) {
    return FORBIDDEN_MESSAGE;
  }
  if (status === 503) {
    return AUTH_SERVICE_UNAVAILABLE_MESSAGE;
  }
  const error = data.error;
  if (typeof error === "string" && error.trim()) {
    return error;
  }
  return fallback;
}

function isRecord(value: unknown): value is ApiResponseData {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
