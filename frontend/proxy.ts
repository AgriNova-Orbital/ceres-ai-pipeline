import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/login(.*)",
  "/register(.*)",
  "/privacy",
  "/terms",
  "/favicon.ico",
  "/logo(.*)",
  "/api/oauth/callback(.*)",
  "/auth(.*)",
]);

const isApiRoute = createRouteMatcher(["/api(.*)"]);

export default clerkMiddleware(async (auth, request) => {
  if (isPublicRoute(request)) {
    return NextResponse.next();
  }

  const authState = await auth();
  if (!authState.userId) {
    if (isApiRoute(request)) {
      return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
    }
    return authState.redirectToSignIn();
  }

  if (isApiRoute(request)) {
    const token = await authState.getToken();
    if (token) {
      const requestHeaders = new Headers(request.headers);
      requestHeaders.set("Authorization", `Bearer ${token}`);
      return NextResponse.next({ request: { headers: requestHeaders } });
    }
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
