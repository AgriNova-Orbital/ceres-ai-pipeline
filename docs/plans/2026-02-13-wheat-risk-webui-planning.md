# Wheat Risk WebUI Planning

## Goal

Provide a single WebUI for end-to-end workflow control:

1. Acquire/refresh source data.
2. Build staged datasets.
3. Run staged training matrix.
4. Evaluate checkpoints and select the best model.

This plan extends the current pipeline scripts and adds a first-class data acquisition interface.

---

## Information Architecture

Recommended top-level tabs:

1. **Data Acquisition**
2. **Dataset Build**
3. **Training Matrix**
4. **Evaluation & Model Selection**
5. **Run History / Logs**

MVP can ship with tabs 1-4 and a simple log panel.

---

## Data Acquisition Interface (New)

### Purpose

Let users expand or change source time ranges without command-line usage.

### Input Controls

- `Stage`: 1/2/3
- `Start Date` / `End Date`
- `AOI BBox`: min_lon, min_lat, max_lon, max_lat
- `EE Project`
- `Drive Folder`
- `Max Cloud (%)`
- `Use Dynamic World` toggle
- `Limit (weeks)` for safe trial runs
- Mode toggle: `Dry Run` / `Run`

### Actions

- **Preview Plan** (dry-run):
  - Runs `scripts/export_weekly_risk_rasters.py ... --dry-run`
  - Returns planned weekly bins and export names.
- **Start Export**:
  - Runs `scripts/export_weekly_risk_rasters.py ... --run`
  - Returns queued task list + task ids.
- **Refresh Inventory**:
  - Runs `scripts/inventory_wheat_dates.py`
  - Displays earliest/latest, expected nodes, missing count, missing date list.

### Validation Rules

- End date must be >= start date.
- Date span must not exceed configured safety window unless user confirms.
- AOI bbox must pass geometric validation.
- `Run` mode requires Drive folder and EE project.

### Output Panel

- Job status (queued/running/done/failed)
- Stdout/stderr log tail
- Summary cards:
  - earliest_date
  - latest_date
  - expected_nodes
  - observed_nodes
  - missing_count

### Image Preview (MVP)

- Add a quicklook viewer next to export controls.
- Preview source rasters by weekly node (date slider + previous/next buttons).
- Support RGB preset and index preset (e.g., NDVI-style pseudo color if available).
- Include AOI bbox overlay so users can verify geographic coverage before export.
- Show basic pixel stats for the current viewport: min/max/mean and non-finite ratio.
- Keep previews lightweight by server-side downsampling to a capped resolution.

---

## Dataset Build Interface

### Inputs

- Input raw dir
- Output dir template (`.../L1`, `.../L2`, `.../L4`)
- `patch_size` / `step_size`
- `expected_weeks`
- `max_patches`
- seed

### Actions

- Build per-level dataset
- Build all levels
- Sample count check (`index.csv` rows per level)

### Image Preview (MVP)

- Add patch preview cards per level (`L1`, `L2`, `L4`).
- Each card shows:
  - one random sampled patch image,
  - patch metadata (level, patch size, week count, NaN ratio),
  - label sequence sparkline preview.
- Add a "Regenerate sample" button to spot-check data quality quickly.

---

## Training Matrix Interface

### Inputs

- Levels (default `1,2,4`)
- Steps (default `100,500,2000`)
- Device / batch / epochs / lr
- Index template / root template

### Actions

- Dry-run matrix order
- Start matrix run (`--run --execute-train`)
- Split run across GPU0/GPU1 (optional profile)

### Outputs

- Per-cell status table
- `summary.csv` link
- failed-cell quick retry buttons

---

## Evaluation Interface

### Inputs

- Summary CSV path
- Index/root templates
- Precision floor
- Label threshold
- Eval ratio/min size

### Actions

- Run evaluation (`scripts/eval_staged_training_matrix.py`)
- Show sortable metrics table
- Highlight recall-first best checkpoint

### Outputs

- `eval_metrics.csv`
- `best_model.json`
- Best threshold + checkpoint path

### Image Preview (MVP)

- Add side-by-side visual comparison for selected model:
  - risk probability heatmap,
  - thresholded binary alert map,
  - optional raw-band quicklook reference.
- Add threshold slider in preview pane and live-update confusion summary.
- Allow selecting level/step checkpoint from table to inspect qualitative differences.

---

## Backend Integration Pattern

- WebUI starts script jobs as subprocess tasks.
- Each run gets a run-id directory for logs and outputs.
- Long jobs stream logs to UI (polling or websocket).
- Keep script contracts stable; UI should not duplicate pipeline logic.

For preview generation:

- Add a small preview service layer that renders cached PNG quicklooks from GeoTIFF/NPZ inputs.
- Cache key should include source file + date/level + preview params to avoid repeated heavy reads.
- Use bounded worker pool so preview rendering cannot starve training jobs.

---

## MVP Delivery Scope

MVP must include:

1. Data Acquisition tab with dry-run/run + inventory refresh.
2. Training Matrix tab with dry-run and run buttons.
3. Evaluation tab that outputs best checkpoint and threshold.
4. Basic run history list with log viewing.

Non-MVP:

- Fine-grained task cancellation
- Multi-user concurrency controls
- Advanced map visualization layers
