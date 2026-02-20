# Wheat Risk 2D Staged Training Design

## Goal

Design a deterministic training workflow with:

1. Data inventory and date completeness checks.
2. A 2D staged training matrix where:
   - Outer loop controls image granularity (Level 1 -> Level 2 -> Level 3).
   - Inner loop controls sample size (Step A -> Step B -> Step C).

The agreed cadence for completeness checks is every 7 days.

---

## Confirmed Decisions

- Date completeness cadence: every 7-day node.
- Image granularity levels:
  - Level 1: 1x (no split)
  - Level 2: 2x2 split
  - Level 3: 4x4 split
- Sample size steps under each level:
  - Step A: 100
  - Step B: 500
  - Step C: 2000
- Execution order must be nested-loop (finish all steps in current level before next level).

---

## Part 1: Data Inventory and Missing-Date Detection

### Objective

Given raw weekly rasters, identify:

- earliest date
- latest date
- expected date nodes (7-day cadence)
- observed date nodes
- missing dates list

### Date-key rules

Use date keys in this priority:

1. Explicit date in filename (`YYYYMMDD` or `YYYY-MM-DD`/`YYYY_MM_DD`).
2. ISO week code (`YYYYWww` -> Monday of that week).
3. Numeric index fallback (`data_001`, `data_002`, ...) + anchor date + 7-day step.

### Outputs

- `reports/data_inventory.json`
  - `earliest_date`, `latest_date`, `expected_nodes`, `observed_nodes`, `missing_count`, `missing_rate`
- `reports/missing_dates.csv`
  - columns: `date`, `position`, `reason`

### Inventory gate

Before training starts:

- Block training if `missing_rate > 0.10`, or
- Block training if max consecutive missing nodes > 2.

---

## Part 2: 2D Staged Training Matrix

### Level-to-patch mapping

Use a base patch size and scale by level split factor:

- Level 1 (1x): patch_size = 64
- Level 2 (2x2): patch_size = 32
- Level 3 (4x4): patch_size = 16

Use matching `step_size` for non-overlap in MVP runs.

### Inner sample steps

For each level, keep validation/test fixed and only increase train subset size:

- Step A: 100
- Step B: 500
- Step C: 2000

Step B must include Step A, and Step C must include Step B (prefix sampling on a fixed shuffled order).

### Required nested-loop order

```
L1-S100 -> L1-S500 -> L1-S2000
L2-S100 -> L2-S500 -> L2-S2000
L3-S100 -> L3-S500 -> L3-S2000
```

No interleaving across levels is allowed.

---

## Run Artifacts

Per cell (`Lx/Sy`) write:

- `runs/staged/Lx/Sy/config.json`
- `runs/staged/Lx/Sy/train.log`
- `runs/staged/Lx/Sy/model.pt`
- `runs/staged/Lx/Sy/metrics.json`

Global summary:

- `runs/staged/summary.csv`
  - columns: `level,step,n_train,status,loss,wall_time_s,checkpoint_path`

---

## Error Handling and Recovery

- If one cell fails, mark it failed and continue to next cell.
- If dataset build fails for a level, skip all steps in that level and continue to next level.
- Keep deterministic seeds for reproducibility.
- For memory safety during patch build, constrain per-process GDAL cache and tune worker count.

---

## MVP Scope (One-Day Constraint)

In MVP mode:

- run inventory once
- run matrix with the agreed 3x3 cells
- log train loss and runtime per cell
- generate one comparable summary table for decision making

Advanced metrics (recall/precision/F2 threshold sweeps) can be attached in the next phase after this baseline matrix is stable.
