# Dashboard Panel Completion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make every dashboard card route to a working panel with job submission, job detail visibility, and useful pipeline output/status feedback.

**Architecture:** Keep Flask as the API/job orchestration layer and Next.js as the protected UI. Fill the smallest missing seams first: add the missing Build Dataset page for existing `/api/run/build`, then surface existing `/api/jobs/<id>` metadata/results across panels, then add only the input controls needed to make existing backend contracts usable from the UI.

**Tech Stack:** Next.js App Router, React, Tailwind CSS, Flask, RQ, Redis, pytest, Node `node:test`.

---

## Current Inventory

| Dashboard entry | Frontend file | Backend/API | Current gap |
| --- | --- | --- | --- |
| Settings | `frontend/app/settings/page.tsx` | `apps/api_oauth.py:142-194` | Works for OAuth setup; keep as dependency for Drive/downloader run actions. |
| Google Drive | `frontend/app/drive/page.tsx` | `apps/wheat_risk_webui.py:900-941`, `apps/api_oauth.py:80-194` | Can list/download, but job detail/result is only visible through Jobs page. |
| Downloader | `frontend/app/downloader/page.tsx` | `apps/api_runs.py:128-179` | `download_all` needs `drive_folder`; backend also supports `ee_project`, but UI does not expose either. |
| Data Ingest | `frontend/app/ingest/page.tsx` | `apps/api_runs.py:528-558`, `apps/api_runs.py:159-177` | Button says ingest but enqueues inventory refresh, not merge/normalize execution. Treat rename/real action as a separate decision; do not silently change pipeline semantics. |
| Data Browser | `frontend/app/data/page.tsx` | `apps/api_runs.py:445-526` | Browses files but does not link paths into Preview. |
| Build Dataset | `frontend/app/dashboard/page.tsx:45` | `apps/api_runs.py:183-215` | Dashboard links to `/build`, but no `frontend/app/build/page.tsx` exists. |
| Training | `frontend/app/training/page.tsx` | `apps/api_runs.py:219-304` | Submits jobs; matrix matching uses broad description matching and does not show job detail/result. |
| Evaluation | `frontend/app/evaluation/page.tsx` | `apps/api_runs.py:308-353` | Only a single button with default backend paths; no form for summary/output/threshold/device inputs. |
| Admin Dashboard | `frontend/app/admin/page.tsx`, `frontend/components/AdminDashboard.tsx` | `apps/api_admin.py:14-133` | Existing admin overview; keep out of first completion slice unless a regression appears. |
| Jobs Monitor | `frontend/app/jobs/page.tsx` | `apps/api_runs.py:357-437` | Lists jobs, but route-level details/progress/result should be reusable by panels. |
| Inventory | `frontend/app/inventory/page.tsx` | `apps/api_runs.py:159-177` | Works as wrapper around inventory refresh, but output is only visible in Jobs. |
| Preview | `frontend/app/preview/page.tsx` | `apps/wheat_risk_webui.py:968-1032` | Manual path entry only; should accept a `path` query param from Data Browser. |

## Implementation Order

1. Fix the broken `/build` dashboard link by adding a minimal Build Dataset panel.
2. Add reusable job detail fetching/presentation so submitted jobs expose progress, return values, and errors without forcing the user to inspect raw queues.
3. Wire submitted job feedback into existing panels using the reusable job detail component.
4. Add required downloader run inputs (`drive_folder`, `ee_project`) and validation for `download_all`.
5. Add evaluation inputs for the backend-supported paths and threshold/device controls.
6. Link Data Browser rows to Preview using a query param and initialize Preview from that param.

## Task 1: Add Missing Build Dataset Page

**Files:**
- Create: `frontend/app/build/page.tsx`
- Test: `tests/test_dashboard_panel_routes.py`

**Step 1: Write the failing route test**

Add this test:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_build_route_has_page() -> None:
    assert (ROOT / "frontend" / "app" / "build" / "page.tsx").exists()


def test_dashboard_links_only_to_existing_app_pages() -> None:
    dashboard = ROOT / "frontend" / "app" / "dashboard" / "page.tsx"
    text = dashboard.read_text(encoding="utf-8")
    for href in sorted(set(part.split('"', 1)[0] for part in text.split('href: "')[1:])):
        if href.startswith("/") and href not in {"/privacy", "/terms"}:
            assert (ROOT / "frontend" / "app" / href.strip("/") / "page.tsx").exists(), href
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev python -m pytest tests/test_dashboard_panel_routes.py -q`

Expected: FAIL because `frontend/app/build/page.tsx` does not exist.

**Step 3: Write minimal implementation**

Create `frontend/app/build/page.tsx` with a form around existing `/api/run/build`:

```tsx
"use client";

import { useState } from "react";
import PageLayout from "@/components/PageLayout";
import FeedbackMessage from "@/components/FeedbackMessage";
import SubmitButton from "@/components/SubmitButton";
import JobPanel from "@/components/JobPanel";
import { useApiSubmit } from "@/lib/useApiSubmit";

export default function BuildPage() {
  const [action, setAction] = useState("dry_run");
  const [level, setLevel] = useState("1");
  const [rawDir, setRawDir] = useState("data/raw/france_2025_weekly");
  const [expectedWeeks, setExpectedWeeks] = useState("46");
  const [maxPatches, setMaxPatches] = useState("12000");
  const [skipExisting, setSkipExisting] = useState(false);
  const { loading, result, error, jobId, submit, clearResult, clearError } = useApiSubmit();

  function handleSubmit() {
    submit("/api/run/build", {
      action,
      level,
      raw_dir: rawDir,
      expected_weeks: Number(expectedWeeks),
      max_patches: Number(maxPatches),
      skip_existing: skipExisting,
    });
  }

  return (
    <PageLayout title="Build Dataset" description="Build staged patch datasets from canonical raw GeoTIFFs.">
      <div className="space-y-6 rounded-lg border bg-white p-6 shadow-sm">
        {(result || error) && (
          <FeedbackMessage message={result || error} type={result ? "success" : "error"} jobId={jobId || undefined} onClear={() => { clearResult(); clearError(); }} />
        )}
        <label className="block text-sm font-medium">
          Action
          <select value={action} onChange={(e) => setAction(e.target.value)} className="mt-1 block w-full rounded border px-3 py-2 text-sm">
            <option value="dry_run">Dry Run</option>
            <option value="build_level">Build Level</option>
          </select>
        </label>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Level" value={level} onChange={setLevel} />
          <Field label="Expected Weeks" value={expectedWeeks} onChange={setExpectedWeeks} />
          <Field label="Max Patches" value={maxPatches} onChange={setMaxPatches} />
          <Field label="Raw Directory" value={rawDir} onChange={setRawDir} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={skipExisting} onChange={(e) => setSkipExisting(e.target.checked)} />
          Skip existing outputs
        </label>
        <SubmitButton loading={loading} onClick={handleSubmit} label="Submit Build Job" loadingLabel="Submitting..." />
      </div>
      <JobPanel />
    </PageLayout>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <input value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 block w-full rounded border px-3 py-2 text-sm" />
    </label>
  );
}
```

**Step 4: Run tests and build**

Run: `uv run --dev python -m pytest tests/test_dashboard_panel_routes.py -q`

Expected: PASS.

Run: `cd frontend && npm run build`

Expected: build succeeds.

**Step 5: Commit**

```bash
git add frontend/app/build/page.tsx tests/test_dashboard_panel_routes.py
git commit -m "feat(frontend): add build dataset panel"
```

## Task 2: Add Reusable Job Detail API Helper

**Files:**
- Create: `frontend/lib/job-detail.ts`
- Create: `frontend/lib/job-detail.test.js`

**Step 1: Write failing tests**

Create `frontend/lib/job-detail.test.js` using the same TypeScript loader pattern as `frontend/lib/api-response.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function loadTypeScriptModule(relativePath) {
  const filename = path.join(__dirname, relativePath);
  const source = fs.readFileSync(filename, 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(compiled, { exports: module.exports, module, require }, { filename });
  return module.exports;
}

const { jobProgressLabel, jobResultSummary } = loadTypeScriptModule('job-detail.ts');

test('jobProgressLabel includes step and progress percent', () => {
  assert.equal(jobProgressLabel({ meta: { step: 'running evaluation', progress: 40 } }), 'running evaluation (40%)');
});

test('jobResultSummary surfaces returned stdout and errors', () => {
  assert.equal(jobResultSummary({ result: { stdout: 'done', stderr: '' } }), 'done');
  assert.equal(jobResultSummary({ error: 'boom' }), 'boom');
});
```

**Step 2: Run test to verify it fails**

Run: `node --test frontend/lib/job-detail.test.js`

Expected: FAIL because `frontend/lib/job-detail.ts` does not exist.

**Step 3: Write minimal implementation**

Create `frontend/lib/job-detail.ts`:

```ts
interface JobLike {
  meta?: Record<string, unknown>;
  result?: Record<string, unknown> | string;
  error?: string;
}

export function jobProgressLabel(job: JobLike): string {
  const step = typeof job.meta?.step === "string" ? job.meta.step : "Waiting for worker";
  const progress = typeof job.meta?.progress === "number" ? ` (${job.meta.progress}%)` : "";
  return `${step}${progress}`;
}

export function jobResultSummary(job: JobLike): string {
  if (job.error) return job.error;
  if (typeof job.result === "string") return job.result;
  if (job.result && typeof job.result.stderr === "string" && job.result.stderr) return job.result.stderr;
  if (job.result && typeof job.result.stdout === "string" && job.result.stdout) return job.result.stdout;
  if (job.result) return JSON.stringify(job.result);
  return "No result yet";
}
```

**Step 4: Run tests**

Run: `node --test frontend/lib/job-detail.test.js frontend/lib/api-response.test.js`

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/lib/job-detail.ts frontend/lib/job-detail.test.js
git commit -m "feat(frontend): add job detail helpers"
```

## Task 3: Surface Job Detail In Submitted Panels

**Files:**
- Create: `frontend/components/JobDetailCard.tsx`
- Modify: `frontend/app/build/page.tsx`
- Modify: `frontend/app/downloader/page.tsx`
- Modify: `frontend/app/evaluation/page.tsx`
- Modify: `frontend/app/inventory/page.tsx`
- Test: `tests/test_dashboard_panel_routes.py`

**Step 1: Write failing static tests**

Add tests that require submitted panels to render `JobDetailCard`:

```python
def test_job_submitting_panels_render_job_detail_card() -> None:
    for rel in [
        "frontend/app/build/page.tsx",
        "frontend/app/downloader/page.tsx",
        "frontend/app/evaluation/page.tsx",
        "frontend/app/inventory/page.tsx",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "JobDetailCard" in text, rel
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev python -m pytest tests/test_dashboard_panel_routes.py::test_job_submitting_panels_render_job_detail_card -q`

Expected: FAIL until panels import and render `JobDetailCard`.

**Step 3: Create `JobDetailCard`**

Use `/api/jobs/<jobId>` and existing `readApiResponse`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import StatusBadge from "@/components/StatusBadge";
import { readApiResponse } from "@/lib/api-response";
import { jobProgressLabel, jobResultSummary } from "@/lib/job-detail";

interface JobDetailCardProps { jobId: string | null; }

export default function JobDetailCard({ jobId }: JobDetailCardProps) {
  const [job, setJob] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const inFlightRef = useRef(false);

  useEffect(() => {
    if (!jobId) return;
    async function load() {
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      try {
        const res = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
        const response = await readApiResponse(res, "Failed to load job detail");
        if (response.ok) {
          setError("");
          setJob(response.data.job as Record<string, unknown>);
        } else {
          setError(response.error);
        }
      } catch {
        setError("Connection error");
      } finally {
        inFlightRef.current = false;
      }
    }
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [jobId]);

  if (!jobId) return null;
  return (
    <section className="rounded-lg border bg-white p-4 text-sm shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold">Latest Job</h2>
        {typeof job?.status === "string" && <StatusBadge status={job.status} />}
      </div>
      <p className="mt-2 font-mono text-xs text-stone-500">{jobId}</p>
      {error ? <p className="mt-3 text-red-600">{error}</p> : null}
      {job ? <p className="mt-3 text-stone-600">{jobProgressLabel(job)}</p> : <p className="mt-3 text-stone-400">Loading job detail...</p>}
      {job ? <pre className="mt-3 max-h-48 overflow-auto rounded bg-stone-950 p-3 text-xs text-stone-100">{jobResultSummary(job)}</pre> : null}
    </section>
  );
}
```

**Step 4: Render `JobDetailCard` in submitted panels**

Import `JobDetailCard` and render `<JobDetailCard jobId={jobId} />` below each form in Build, Downloader, Evaluation, and Inventory.

**Step 5: Run tests and build**

Run: `uv run --dev python -m pytest tests/test_dashboard_panel_routes.py -q`

Run: `node --test frontend/lib/*.test.js`

Run: `cd frontend && npm run build`

Expected: all pass.

**Step 6: Commit**

```bash
git add frontend/components/JobDetailCard.tsx frontend/app/build/page.tsx frontend/app/downloader/page.tsx frontend/app/evaluation/page.tsx frontend/app/inventory/page.tsx tests/test_dashboard_panel_routes.py
git commit -m "feat(frontend): show submitted job details"
```

## Task 4: Complete Downloader Inputs For Run Actions

**Files:**
- Modify: `frontend/app/downloader/page.tsx`
- Test: `tests/test_dashboard_panel_routes.py`

**Step 1: Write failing static tests**

```python
def test_downloader_exposes_required_run_inputs() -> None:
    text = (ROOT / "frontend" / "app" / "downloader" / "page.tsx").read_text(encoding="utf-8")
    assert "driveFolder" in text
    assert "eeProject" in text
    assert "drive_folder" in text
    assert "ee_project" in text
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev python -m pytest tests/test_dashboard_panel_routes.py::test_downloader_exposes_required_run_inputs -q`

Expected: FAIL because `driveFolder` and `eeProject` are absent.

**Step 3: Implement minimal UI and validation**

Add state and submit payload:

```tsx
const [driveFolder, setDriveFolder] = useState("");
const [eeProject, setEeProject] = useState("");

function handleSubmit() {
  if ((action === "download_all" || action === "run_export") && !driveFolder.trim()) {
    clearResult();
    clearError();
    return;
  }
  submit("/api/run/downloader", {
    action,
    stage,
    start_date: startDate,
    end_date: endDate,
    limit,
    drive_folder: driveFolder,
    ee_project: eeProject,
  });
}
```

Add two fields near the date inputs:

```tsx
<Field label="Drive Folder ID" value={driveFolder} onChange={setDriveFolder} />
<Field label="Earth Engine Project" value={eeProject} onChange={setEeProject} />
```

If the validation branch needs visible error, extend local state rather than overloading `useApiSubmit`.

**Step 4: Run tests and build**

Run: `uv run --dev python -m pytest tests/test_dashboard_panel_routes.py -q`

Run: `cd frontend && npm run build`

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/app/downloader/page.tsx tests/test_dashboard_panel_routes.py
git commit -m "feat(frontend): expose downloader run inputs"
```

## Task 5: Add Evaluation Configuration Inputs

**Files:**
- Modify: `frontend/app/evaluation/page.tsx`
- Test: `tests/test_dashboard_panel_routes.py`

**Step 1: Write failing static tests**

```python
def test_evaluation_exposes_backend_supported_inputs() -> None:
    text = (ROOT / "frontend" / "app" / "evaluation" / "page.tsx").read_text(encoding="utf-8")
    for token in ["summaryCsv", "precisionFloor", "labelThreshold", "device", "summary_csv", "precision_floor", "label_threshold"]:
        assert token in text
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev python -m pytest tests/test_dashboard_panel_routes.py::test_evaluation_exposes_backend_supported_inputs -q`

Expected: FAIL because the page only submits defaults.

**Step 3: Implement minimal form**

Add state:

```tsx
const [summaryCsv, setSummaryCsv] = useState("runs/staged_final/summary.csv");
const [precisionFloor, setPrecisionFloor] = useState("0.35");
const [labelThreshold, setLabelThreshold] = useState("0.5");
const [device, setDevice] = useState("cpu");
```

Submit existing backend keys:

```tsx
submit("/api/run/eval", {
  action: "run_eval",
  summary_csv: summaryCsv,
  precision_floor: Number(precisionFloor),
  label_threshold: Number(labelThreshold),
  device,
});
```

Add simple `<Field />` controls for these values and reuse the local `Field` function from Build/Downloader where practical.

**Step 4: Run tests and build**

Run: `uv run --dev python -m pytest tests/test_dashboard_panel_routes.py -q`

Run: `cd frontend && npm run build`

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/app/evaluation/page.tsx tests/test_dashboard_panel_routes.py
git commit -m "feat(frontend): configure evaluation jobs"
```

## Task 6: Link Data Browser Rows To Preview

**Files:**
- Modify: `frontend/app/data/page.tsx`
- Modify: `frontend/app/preview/page.tsx`
- Test: `tests/test_dashboard_panel_routes.py`

**Step 1: Write failing static tests**

```python
def test_data_browser_links_files_to_preview() -> None:
    data_page = (ROOT / "frontend" / "app" / "data" / "page.tsx").read_text(encoding="utf-8")
    preview_page = (ROOT / "frontend" / "app" / "preview" / "page.tsx").read_text(encoding="utf-8")
    assert "href={`/preview?" in data_page
    assert "useSearchParams" in preview_page
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev python -m pytest tests/test_dashboard_panel_routes.py::test_data_browser_links_files_to_preview -q`

Expected: FAIL because Preview is manual-only.

**Step 3: Add links and query initialization**

In `FileTable`, wrap each file name with a link:

```tsx
<Link href={`/preview?type=${f.name.endsWith(".npz") ? "patch" : "raw"}&path=${encodeURIComponent(f.path)}`} className="font-mono text-xs text-emerald-700 hover:underline">
  {f.name}
</Link>
```

In Preview, initialize from search params:

```tsx
import { useSearchParams } from "next/navigation";

const searchParams = useSearchParams();
const initialType = searchParams.get("type") === "patch" ? "patch" : "raw";
const [type, setType] = useState<"raw" | "patch">(initialType);
const [path, setPath] = useState(searchParams.get("path") || "");
```

**Step 4: Run tests and build**

Run: `uv run --dev python -m pytest tests/test_dashboard_panel_routes.py -q`
Run: `cd frontend && npm run build`

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/app/data/page.tsx frontend/app/preview/page.tsx tests/test_dashboard_panel_routes.py
git commit -m "feat(frontend): link data files to preview"
```

## Task 7: Final Verification

**Files:**
- No edits unless verification reveals a defect.

**Step 1: Run backend tests**

Run: `uv run --dev python -m pytest -q`

Expected: all existing tests pass.

**Step 2: Run frontend unit tests**

Run: `node --test frontend/*.test.js frontend/lib/*.test.js`

Expected: all frontend Node tests pass.

**Step 3: Run frontend build**

Run: `cd frontend && npm run build`

Expected: Next build succeeds.

**Step 4: Run compose config check**

Run: `docker compose --profile dev --profile beta --profile release config --quiet`

Expected: no output and exit code 0.

**Step 5: Commit any verification fixes**

Only commit if a fix was required:

```bash
git add <fixed-files>
git commit -m "fix(frontend): stabilize dashboard panels"
```

## Explicit Non-Goals For This Plan

- Do not rename Data Ingest to Inventory or change it to run merge/normalize until the desired backend behavior is confirmed.
- Do not add job cancellation.
- Do not add websockets; polling existing job endpoints is enough for this slice.
- Do not rewrite Admin Dashboard styling or backend admin APIs.
- Do not change persisted data formats.
