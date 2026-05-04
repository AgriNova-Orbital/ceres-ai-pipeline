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
    assert "getToken" in proxy
    assert "Authorization" in proxy
    assert "NextResponse.next" in proxy


def test_next14_middleware_reexports_clerk_proxy() -> None:
    middleware = (FRONTEND / "middleware.ts").read_text()

    assert 'from "./proxy"' in middleware
    assert "export { default, config }" in middleware


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
