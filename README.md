# MechAI — Assembly Line Efficiency Analyzer

**Lean manufacturing analysis tool for real factory floor data.** Load a project, run a full 12-section analysis — from ASME Flow Process Charts to ML-based bottleneck forecasting — and export a print-ready PDF report.

Built for: Python · Flask · Plotly · scikit-learn · Lean Manufacturing · Work & Method Study

---

## What it does

Enter a workstation time study once (station names, cycle times, operator counts) and MechAI auto-derives a full 12-module factory efficiency report:

| # | Module | What it generates |
|---|--------|--------------------|
| 01 | AS-IS Summary | Standard time, normal time, takt time, bottleneck station, line/balance efficiency, NVA steps, units/shift |
| 02 | Flow Process Chart | ASME symbols (Operation, Transport, Inspection, Delay, Storage), zigzag flow, distance, lean recommendations |
| 03 | Line Balance Chart | Cycle time per station vs. takt line, bottleneck highlighted, idle time per station |
| 04 | Plant Layout Generator | 5 layout types — AS-IS (with backtracking), U-Shape, Process, Mixed, Static — interactive Plotly diagrams |
| 05 | Efficiency Comparison | Current vs. optimised across 4 charts (cycle time, KPIs, VA/NVA split, improvement summary) |
| 06 | SOP Generator | Standard Operating Procedure card per workstation — who/what/where/when, steps, safety, quality checks |
| 07 | Cost Calculator | Converts cycle time to ₹ cost; editable wage/worker/overhead; savings per unit/shift/day/month |
| 08 | Daily Production Report (DPR) | Editable shift-level table — qty planned/produced, dispatch time, EOD inventory |
| 09 | Shop Production Schedule | Gantt chart across shop sections for one full shift |
| 10 | ABC Inventory Analysis | A/B/C classification by annual value, Pareto chart, donut chart, replenishment strategy |
| 11 | Kanban Cards | Production pull-system cards for A/B items — part no., reorder point, max stock, supplier, bin location |
| 12 | ML Predictions | 4 scikit-learn regression models — Bottleneck Forecast, Output Forecast, Idle Time Prediction, Stockout Risk |

Every chart is interactive (Plotly) and the whole report exports to a single PDF via the browser's print pipeline.

---

## Tech stack

- **Backend:** Flask 3.x, Python 3.11
- **Data:** pandas, NumPy, CSV-based project storage (no database)
- **Charts:** Plotly 5.x (server-generates figure JSON, client renders)
- **ML:** scikit-learn (LinearRegression, Ridge, Polynomial, MinMaxScaler) trained on station-level data at request time
- **AI Chat:** SmolLM2-360M-Instruct (HuggingFace), runs fully offline after a one-time ~720 MB download
- **Frontend:** Single-page vanilla HTML/CSS/JS (`templates/index.html`), no build step, no framework

---

## Project structure

```
MechAI/
├── app.py              # Flask routes — project CRUD, analysis endpoints, predictions, chat
├── analysis.py          # All chart/report generation logic (Plotly figures, ABC/Kanban/cost calc, ML predictors)
├── insight_engine.py    # Offline LLM chat engine (SmolLM2-360M) with jailbreak-resistant system prompt
├── launch.py             # Standalone entry point — bootstraps the chat model, opens the browser, starts Flask
├── README.md             # Project documentation
├── requirements.txt
├── projects/             # Saved project CSVs (one file per factory line)
│   └── Cooler_Manufacturer_Indore.csv
├── static/
│   └── logo.png
│   └── hero-bg.png
└── templates/
    └── index.html        # Full single-page UI (dashboard, new-project wizard, SOP/PDF modals, chat)
```

---

## Getting started

### Prerequisites
- Python 3.11+
- ~1 GB free disk space (for the offline chat model, downloaded on first run)

### Install

```bash
cd MechAI
pip install -r requirements.txt
```

### Run

```bash
python launch.py
```

This starts a local Flask server at **http://localhost:5000** and opens it in your default browser automatically. On first launch it also downloads the SmolLM2-360M chat model in the background (one-time, ~720 MB, requires internet); after that, MechAI Intelligence runs fully offline.

Alternatively, for development:

```bash
python app.py
```

(runs Flask directly without the model-bootstrap/browser-launch wrapper, useful when iterating on the chat engine separately)

---

## Data model

Projects are stored as flat CSV files in `projects/`, with three row types distinguished by a `section` column:

```csv
section,col1,col2,col3,col4,col5,col6,col7,col8,col9,col10,col11,col12,col13
META,Project_Name,Product_Name,Factory_Type,Location,ShiftMins,TargetOutput,ShiftsPerDay,WorkDaysMonth,PerfRating%,Allowance%,Wage/Hr,Workers,Overhead/Hr
STATION,#,Station_Name,Operators,Time(sec),Type,Component,Distance(ft)
COMPONENT,Name,UnitCost,AnnualUsage,LeadTime,Supplier,Location,ReorderQty,MaxStock
```

- **META** (one row) — project metadata: shift length, target output, performance rating, allowance %, wage and overhead baselines.
- **STATION** (one row per workstation) — name, operator count, observed cycle time in seconds, type (`Operation` / `Inspection` / `Delay` / `Transport`), linked component, and distance to next station. This is the only required input — everything else (NVA%, layout, schedule, SOPs) is auto-derived from it.
- **COMPONENT** (one row per part, optional) — unlocks ABC Inventory Analysis and Kanban Cards when filled in.

New projects can be created through the in-app **New Project** wizard (3 steps: Setup → Workstations → Components) or by dropping a correctly-formatted CSV into `projects/`.

---

## Key API endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/` | Serves the main single-page dashboard |
| GET | `/api/projects` | List saved project CSVs |
| GET | `/api/project/<filename>` | Project meta summary (station count, takt time, bottleneck, etc.) |
| GET | `/api/project_data/<filename>` | Raw project CSV rows (META/STATION/COMPONENT) for editing |
| GET | `/api/analysis/full/<filename>` | Runs all 12 modules and returns combined JSON (drives the main dashboard) |
| GET | `/api/analysis/layout/<filename>/<type>` | Single layout diagram — `type` ∈ `current`, `product`, `process`, `mixed`, `static` |
| POST | `/api/analysis/cost/<filename>` | Recalculates the Module 07 cost breakdown with live wage/worker/overhead inputs |
| POST | `/api/predictions/<filename>` | Runs the 4 ML models for Module 12, accepts what-if scenario inputs |
| POST | `/api/save_project` | Create/update a project from the New Project wizard |
| DELETE | `/api/delete_project/<filename>` | Remove a project |
| POST | `/api/import_csv` | Import a project from raw CSV content |
| GET | `/api/model_status` | Chat model load state (ready / loading / not downloaded) |
| POST | `/api/chat` | Ask MechAI Intelligence a question about the currently loaded factory data |

---

## ML Predictions (Module 12)

Four scikit-learn models are trained on-the-fly from the current project's station data:

1. **Bottleneck Forecast** — sweeps target output upward and shows which station(s) cross the takt line first.
2. **Output Forecaster** — predicts units/shift under what-if scenarios (added operators, performance improvement, station splitting).
3. **Idle Time Predictor** — cumulative capacity wasted across a range of demand targets.
4. **Stockout Risk Scorer** — MinMaxScaler-weighted risk score per component (cost 50% · lead time 35% · demand variability 15%), classified High/Medium/Low.

All four charts update live as the user adjusts demand target, operators-to-add, station-to-split, and demand-variability inputs.

---

## AI Chat — MechAI Intelligence

An offline assistant (SmolLM2-360M-Instruct) embedded in the dashboard, scoped strictly to the loaded factory data via a hardened system prompt. It will:

- Discuss only the OEE/takt/cycle-time/bottleneck data from the currently selected project
- Refuse unrelated requests (general knowledge, code generation, creative writing, etc.)
- Interpret efficiency numbers honestly against fixed benchmarks (e.g. never call <50% line efficiency "acceptable")
- Resist prompt-injection attempts to override its scope

Quick-action buttons (`Worst bottleneck?`, `Explain OEE`, `Takt compliance`, `ML prediction`, `Reduce cycle time`, `Full summary`) are provided for common queries. Responses are capped at ~500 words (trimmed at the nearest sentence boundary) so answers stay concise without cutting off mid-sentence.

---

## Exporting reports

Click **Export PDF** (or **Export Full Report PDF** from the chat tab) to print the full analysis via the browser's native print dialog, in **portrait orientation** (default). The export includes the About, Dashboard, and Links tabs — the AI Chat tab is deliberately excluded from print (an empty/unused chat panel would otherwise waste pages). Print-specific CSS forces all chart backgrounds/colors to render correctly and ensures every plant layout type (Module 04) is included — not just the one currently active on screen.

---

## Notes

- Demo project included: `Cooler_Manufacturer_Indore.csv` — a 17-station desert air cooler assembly line based on real time-study field data.
- The app is single-machine/local-first by design — no auth, no cloud sync, CSVs are the source of truth.
- Packaging with PyInstaller for a standalone desktop executable is planned but not yet wired into this codebase.
