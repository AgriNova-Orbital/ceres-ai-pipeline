# Next.js Frontend Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Flask Jinja2 templates with Next.js + React + Tailwind frontend, Flask becomes pure API backend.

**Architecture:** Flask serves REST API on :5055, Next.js serves UI on :3000 (dev) or :3000 (prod). Next.js proxies `/api/*` to Flask. Auth uses HTTP-only cookies set by Flask, read by both.

**Tech Stack:** Next.js 14 (App Router), React 18, Tailwind CSS 3, Flask (API mode), Docker

---

## Task 1: Initialize Next.js Project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/tsconfig.json`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/globals.css`

**Step 1: Create Next.js project structure**

```bash
mkdir -p frontend/app frontend/components frontend/lib
```

**Step 2: Write package.json**

```json
{
  "name": "ceres-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.4.0"
  }
}
```

**Step 3: Write next.config.js**

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    const apiUrl = process.env.API_URL || "http://localhost:5055";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
      {
        source: "/auth/:path*",
        destination: `${apiUrl}/auth/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
```

**Step 4: Write tailwind.config.js, postcss.config.js, tsconfig.json**

Standard configs for Next.js + Tailwind.

**Step 5: Install dependencies**

Run: `cd frontend && npm install`

**Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: initialize Next.js frontend project"
```

## Task 2: Create Flask API Endpoints

**Files:**
- Create: `apps/api_auth.py`
- Modify: `apps/wheat_risk_webui.py` (mount API blueprints)

**Step 1: Write auth API blueprint**

`apps/api_auth.py` - Flask Blueprint with:
- `POST /api/auth/login` - returns JSON { user, token }
- `POST /api/auth/logout` - clears session
- `POST /api/auth/change-password` - returns JSON success
- `GET /api/auth/me` - returns current user or 401

**Step 2: Mount blueprint in create_app()**

**Step 3: Test API endpoints with curl**

Run: `curl -X POST http://localhost:5055/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin"}'`

**Step 4: Commit**

## Task 3: Build Login Page

**Files:**
- Create: `frontend/app/login/page.tsx`
- Create: `frontend/components/LoginForm.tsx`

**Step 1: Write LoginForm component**

React form with username/password fields, POST to `/api/auth/login`.

**Step 2: Write login page**

Uses LoginForm, redirects to `/` on success, shows error on failure.

**Step 3: Test in browser**

Run: `cd frontend && npm run dev`, visit `http://localhost:3000/login`

**Step 4: Commit**

## Task 4: Build Change Password Page

**Files:**
- Create: `frontend/app/change-password/page.tsx`
- Create: `frontend/components/ChangePasswordForm.tsx`

**Step 1: Write ChangePasswordForm component**

**Step 2: Write change-password page**

**Step 3: Test flow: login → change password → redirect to home**

**Step 4: Commit**

## Task 5: Build Auth Middleware for Next.js

**Files:**
- Create: `frontend/middleware.ts`

**Step 1: Write middleware.ts**

Checks auth cookie, redirects unauthenticated users to `/login`, redirects default-password users to `/change-password`.

**Step 2: Test protected routes**

**Step 3: Commit**

## Task 6: Build Home/Dashboard Page

**Files:**
- Create: `frontend/app/page.tsx`
- Create: `frontend/components/Dashboard.tsx`
- Create: `frontend/components/Navigation.tsx`

**Step 1: Write Navigation component**

Sidebar with links to all sections.

**Step 2: Write Dashboard component**

Basic/Advanced mode toggle, welcome message, quick actions.

**Step 3: Write home page**

**Step 4: Commit**

## Task 7: Docker Integration

**Files:**
- Create: `frontend/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `Dockerfile` (add node build step or separate service)

**Step 1: Write frontend Dockerfile**

Multi-stage: build Next.js, serve with `next start`.

**Step 2: Add frontend service to docker-compose.yml**

**Step 3: Update Flask to serve API only (disable template rendering)**

**Step 4: Test full stack in Docker**

**Step 5: Commit**

## Task 8: E2E Test with Brave

**Files:**
- Modify: `tests/e2e/test_webui_full_flow.py`

**Step 1: Update E2E tests to target Next.js frontend**

**Step 2: Run tests**

**Step 3: Commit**
