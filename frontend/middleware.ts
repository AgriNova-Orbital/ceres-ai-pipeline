import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_EXACT_PATHS = ["/", "/login", "/register", "/privacy", "/terms", "/favicon.ico"];
const PUBLIC_PREFIX_PATHS = ["/logo/"];
const API_PATHS = ["/api/", "/auth/"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip API/auth routes and explicitly public pages/assets
  if (
    API_PATHS.some((p) => pathname.startsWith(p)) ||
    PUBLIC_EXACT_PATHS.includes(pathname) ||
    PUBLIC_PREFIX_PATHS.some((p) => pathname.startsWith(p))
  ) {
    return NextResponse.next();
  }

  // Check auth via Flask backend
  const apiUrl = process.env.API_URL || "http://localhost:5055";
  try {
    const cookieHeader = request.headers.get("cookie") || "";
    const res = await fetch(`${apiUrl}/api/auth/me`, {
      headers: { cookie: cookieHeader },
    });

    if (res.status === 401) {
      return NextResponse.redirect(new URL("/login", request.url));
    }

    const data = await res.json();
    if (data.requiresPasswordChange && pathname !== "/change-password") {
      return NextResponse.redirect(new URL("/change-password", request.url));
    }
  } catch {
    // Backend unavailable - redirect to login
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
