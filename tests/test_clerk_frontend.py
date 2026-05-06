from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_clerk_nextjs_dependency_is_declared() -> None:
    package_json = json.loads((FRONTEND / "package.json").read_text())

    assert "@clerk/nextjs" in package_json["dependencies"]


def test_clerk_proxy_uses_clerk_middleware() -> None:
    proxy = (FRONTEND / "proxy.ts").read_text()

    assert "clerkMiddleware" in proxy
    assert "@clerk/nextjs/server" in proxy
    assert "authMiddleware" not in proxy
    assert "export const config" in proxy
    assert "matcher" in proxy


def test_clerk_proxy_injects_bearer_for_api_rewrites() -> None:
    proxy = (FRONTEND / "proxy.ts").read_text()

    assert '  "/api(.*)",' not in proxy
    assert '"/api/auth(.*)"' not in proxy
    assert "getToken" in proxy
    assert "Authorization" in proxy
    assert "NextResponse.next" in proxy


def test_clerk_proxy_returns_json_unauthorized_for_api_requests() -> None:
    proxy = (FRONTEND / "proxy.ts").read_text()

    assert "auth.protect()" not in proxy
    assert "NextResponse.json" in proxy
    assert "Not authenticated" in proxy
    assert "status: 401" in proxy


def test_next14_middleware_reexports_clerk_proxy() -> None:
    middleware = (FRONTEND / "middleware.ts").read_text()

    assert 'from "./proxy"' in middleware
    assert "export { default }" in middleware


def test_middleware_declares_static_asset_exclusions_directly() -> None:
    middleware = (FRONTEND / "middleware.ts").read_text()

    assert "export const config" in middleware
    assert "matcher" in middleware
    assert "_next/static" in middleware
    assert "_next/image" in middleware
    assert "favicon.ico" in middleware


def test_layout_wraps_body_with_clerk_provider_and_buttons() -> None:
    layout = (FRONTEND / "app" / "layout.tsx").read_text()
    auth_controls = (FRONTEND / "components" / "ClerkAuthControls.tsx").read_text()

    assert "ClerkProvider" in layout
    assert "ClerkAuthControls" in layout
    assert "Show" in auth_controls
    assert "SignInButton" in auth_controls
    assert "SignUpButton" in auth_controls
    assert "UserButton" in auth_controls
    assert "<body>" in layout
    assert layout.index("<body>") < layout.index("<ClerkProvider")
    assert "{children}" in layout
    assert layout.index("<ClerkProvider") < layout.index("<ClerkAuthControls")


def test_layout_does_not_render_clerk_controls_without_provider() -> None:
    layout = (FRONTEND / "app" / "layout.tsx").read_text()

    assert "clerkPublishableKey ?" in layout
    assert "<ClerkAuthControls />" in layout
    assert "<>\n            <ThemeBoot />\n            {children}\n          </>" in layout


def test_clerk_uses_current_app_router_apis_only() -> None:
    frontend_sources = "\n".join(
        p.read_text()
        for p in [
            FRONTEND / "proxy.ts",
            FRONTEND / "middleware.ts",
            FRONTEND / "app" / "layout.tsx",
            FRONTEND / "app" / "login" / "page.tsx",
            FRONTEND / "app" / "register" / "page.tsx",
            FRONTEND / "components" / "ClerkAuthControls.tsx",
        ]
    )

    assert "authMiddleware" not in frontend_sources
    assert "<SignedIn" not in frontend_sources
    assert "<SignedOut" not in frontend_sources
    assert " SignedIn" not in frontend_sources
    assert " SignedOut" not in frontend_sources
    assert "withAuth" not in frontend_sources
    assert "_app.tsx" not in frontend_sources


def test_clerk_env_placeholders_are_documented() -> None:
    env_example = (ROOT / ".env.example").read_text()

    assert "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=" in env_example
    assert "CLERK_SECRET_KEY=" in env_example


def test_login_and_register_pages_use_clerk_components() -> None:
    login = (FRONTEND / "app" / "login" / "page.tsx").read_text()
    register = (FRONTEND / "app" / "register" / "page.tsx").read_text()

    assert "SignIn" in login
    assert "@clerk/nextjs" in login
    assert "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" in login
    assert "Clerk is not configured" in login
    assert "LoginForm" not in login
    assert "/api/auth/login" not in login

    assert "SignUp" in register
    assert "@clerk/nextjs" in register
    assert "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" in register
    assert "Clerk is not configured" in register
    assert "/api/auth/register" not in register
    assert "Create Admin Account" not in register


def test_public_landing_page_does_not_prefetch_protected_dashboard() -> None:
    landing = (FRONTEND / "app" / "page.tsx").read_text()

    assert 'href="/dashboard"' in landing
    assert 'prefetch={false}' in landing


def test_logout_uses_clerk_sign_out_instead_of_legacy_api() -> None:
    logout = (FRONTEND / "components" / "LogoutButton.tsx").read_text()
    admin = (FRONTEND / "components" / "AdminDashboard.tsx").read_text()

    assert "useClerk" in logout
    assert "signOut" in logout
    assert 'redirectUrl: "/login"' in logout
    assert "/api/auth/logout" not in logout

    assert "LogoutButton" in admin
    assert "function LogoutBtn" not in admin
    assert "/api/auth/logout" not in admin


def test_frontend_removes_legacy_password_auth_forms() -> None:
    frontend_pages_and_components = "\n".join(
        p.read_text()
        for directory in [FRONTEND / "app", FRONTEND / "components"]
        for p in directory.rglob("*.tsx")
    )
    change_password_page = (FRONTEND / "app" / "change-password" / "page.tsx").read_text()

    assert "/api/auth/login" not in frontend_pages_and_components
    assert "/api/auth/logout" not in frontend_pages_and_components
    assert "/api/auth/change-password" not in frontend_pages_and_components
    assert "LoginForm" not in frontend_pages_and_components
    assert "ChangePasswordForm" not in change_password_page


def test_protected_api_responses_use_shared_auth_error_handling() -> None:
    helper = FRONTEND / "lib" / "api-response.ts"
    assert helper.exists()

    helper_source = helper.read_text()
    assert "Your sign-in session expired" in helper_source
    assert "Authentication service is temporarily unavailable" in helper_source
    assert "content-type" in helper_source.lower()

    for relative in [
        "lib/useApiSubmit.ts",
        "components/JobPanel.tsx",
        "components/AdminDashboard.tsx",
        "app/settings/page.tsx",
        "app/drive/page.tsx",
        "app/jobs/page.tsx",
        "app/training/page.tsx",
        "app/ingest/page.tsx",
        "app/data/page.tsx",
    ]:
        source = (FRONTEND / relative).read_text()
        assert "readApiResponse" in source


def test_protected_frontend_api_calls_do_not_parse_responses_directly() -> None:
    for directory in [FRONTEND / "app", FRONTEND / "components", FRONTEND / "lib"]:
        for source_path in directory.rglob("*.tsx"):
            assert ".json()" not in source_path.read_text(), source_path.relative_to(FRONTEND)

    for source_path in [FRONTEND / "lib" / "useApiSubmit.ts"]:
        assert ".json()" not in source_path.read_text(), source_path.relative_to(FRONTEND)


def test_ingest_status_load_clears_loading_after_api_errors() -> None:
    source = (FRONTEND / "app" / "ingest" / "page.tsx").read_text()
    start = source.index("async function loadStatus")
    load_status = source[start : source.index("useEffect", start)]

    assert "finally" in load_status
    assert "setLoading(false);" in load_status
