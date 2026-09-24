# tinting-voxel - Project Instructions

## Overview

Image-to-STL/3MF color block converter that transforms images into layered 3D-printable files using CMYK color separation with Beer-Lambert optical modeling. Supports N-color filament configurations, batch processing, and multiple output formats.

## Tech Stack

- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS + three.js
- **Backend**: Python 3 + FastAPI + numpy-stl + PIL + scikit-learn
- **Testing**: pytest (backend), Vitest (frontend), Playwright (E2E)
- **Deploy**: Docker, Railway, Fly.io

## Project Structure

```
tinting-voxel/
├── backend/              # Python FastAPI backend
│   ├── main.py           # Application entry point
│   ├── api/              # API routes and models
│   │   ├── models.py     # Pydantic data models (FilamentConfigMixin)
│   │   ├── error_handlers.py  # @handle_api_errors decorator
│   │   ├── validators.py # File upload validation
│   │   ├── rate_limiter.py # slowapi limiter instance
│   │   └── routes/       # Route handlers
│   │       ├── image.py      # Image processing (pixel/SVG modes)
│   │       ├── download.py   # CSV download endpoint
│   │       ├── download_v2.py # V2 N-color endpoints (STL, SVG-STL, 3MF, SVG-3MF, print settings)
│   │       ├── filament.py   # Filament preview
│   │       ├── batch.py      # Batch processing (up to 20 images)
│   │       ├── palette.py    # Palette library
│   │       ├── param_search.py # Background parameter search + candidate previews
│   │       ├── bug_report.py  # In-app bug reports (storage + optional email)
│   │       ├── events.py     # Browser usage events
│   │       └── health.py     # Health check endpoints
│   ├── core/             # Core algorithms
│   │   ├── blend_color.py    # Color blending (Beer-Lambert model)
│   │   ├── blend_models.py   # Unified blend formula + vectorized batch
│   │   ├── code_grid.py      # Code grid generation utilities
│   │   ├── color_config.py   # Filament presets (single source of truth)
│   │   ├── color_materials.py # Material properties (hex + scalar or RGB TD)
│   │   ├── grid_sampling.py  # Code-grid RGB assembly for blend fitting
│   │   └── palette_library.py # Supported filament palettes
│   ├── services/         # Business logic
│   │   ├── analytics.py         # In-memory usage analytics
│   │   ├── telemetry.py         # Structured usage/operations events
│   │   ├── bug_report.py       # Bug report storage + optional email delivery
│   │   ├── batch_processor.py    # Multi-image batch processing
│   │   ├── csv_generator.py      # CSV export
│   │   ├── filament_preview.py   # Color matrix preview
│   │   ├── image_processor.py    # Image processing + auto-downscale
│   │   ├── label_map.py          # Model-grid label maps (export/preview payloads)
│   │   ├── matrix_cache.py       # Reference-matrix cache (powers /api/cache-stats)
│   │   ├── mesh_optimizer.py     # Greedy meshing optimization
│   │   ├── param_search_service.py # Auto parameter sweep engine
│   │   ├── print_settings_generator.py # Slicer settings JSON
│   │   ├── print_stack.py       # Print stack modeling
│   │   ├── raster_cleanup.py    # Raster post-processing cleanup
│   │   ├── stl_generator.py      # STL file generation
│   │   ├── svg_stl_generator.py  # SVG-mode STL generation
│   │   ├── threemf_generator.py  # 3MF output (one object, a part per filament)
│   │   ├── threemf_writer.py     # 3MF packaging (streamed XML, shared vertices)
│   │   └── vector_processor.py   # Vector/contour processing
│   ├── config/           # Configuration (settings, constants, logging_setup)
│   └── tests/            # Test suite (~770 tests)
│       ├── unit/             # Unit tests
│       ├── integration/      # Integration tests
│       ├── performance/      # Performance tests
│       └── fixtures/
│           ├── images/        # Committed small test images (200-500px, <100KB)
│           └── images-local/  # Gitignored large images for local manual testing
├── src/                  # React frontend
│   ├── main.tsx          # Entry point
│   ├── pages/            # Page components
│   ├── components/       # UI components (25+ components)
│   │   ├── ThreeDPreview.tsx     # WebGL 3D preview (three.js)
│   │   ├── BatchProcessor.tsx    # Batch image processing UI
│   │   ├── PaletteLibrary.tsx    # Palette selection UI
│   │   ├── FilamentConfigPanel.tsx # N-color filament config
│   │   └── ImageEditor.tsx       # Canvas crop/resize editor
│   ├── hooks/            # Custom hooks
│   ├── utils/            # Shared helpers (model grid, telemetry, bug reports)
│   ├── i18n/             # Locale runtime and feature translations (en, zh-CN)
│   └── api/              # API client + types
├── e2e/                  # Playwright E2E tests (8 spec files, 49 tests)
├── Dockerfile            # Multi-stage Docker build
├── docker-compose.yml    # Docker Compose config
├── fly.toml              # Fly.io deploy config
└── railway.toml          # Railway deploy config
```

## Development Commands

### Backend

```bash
cd backend
source .venv/bin/activate

# Run server
uvicorn main:app --reload --port 8000

# Run tests
pytest
pytest tests/unit/test_blend_color.py -v  # specific test

# Run with coverage
pytest --cov
```

### Frontend

```bash
npm run dev          # Development server
npm run build        # Production build
npx tsc --noEmit     # Type check
npm test             # Vitest unit tests
npx playwright test  # E2E tests
```

### Docker

```bash
docker compose up --build  # Build and run
```

## Key URLs

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## API Endpoints

### Image Processing and CSV
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/process-image` | Process image (pixel/SVG modes) |
| POST | `/api/simulate-preview` | Refresh the pixel-mode simulated print preview |
| POST | `/api/download-csv` | Download color data as CSV |

### V2 (N-Color Support)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/download-stl` | STL ZIP with configurable colors |
| POST | `/api/v2/download-svg-stl` | SVG-mode STL with configurable colors |
| POST | `/api/v2/download-3mf` | 3MF: one object with a named, colored part per filament |
| POST | `/api/v2/download-svg-3mf` | SVG-mode 3MF with configurable colors |
| POST | `/api/v2/print-settings` | JSON print settings for slicers |
| GET | `/api/v2/filament-presets` | List available filament presets |
| POST | `/api/v2/layer-limit` | Largest color-layer count a filament set can search |

### Other
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/filament-preview` | Color matrix preview |
| POST | `/api/batch/process` | Batch process up to 20 images |
| POST | `/api/batch/download-stl` | Batch STL download |
| POST | `/api/bug-report` | Submit in-app bug report (optional screenshot) |
| POST | `/api/param-search` | Start one search job and return its ID immediately |
| GET | `/api/param-search/progress/{job_id}` | Poll incremental candidate previews and job status |
| DELETE | `/api/param-search/progress/{job_id}` | Cancel the search job |
| GET | `/api/palettes/` | List color palettes |
| GET | `/api/palettes/{id}` | Get specific palette |
| POST | `/api/events` | Browser usage events (batched, anonymous) |
| GET | `/api/analytics` | Usage analytics |
| GET | `/api/cache-stats` | Reference-matrix cache stats |
| GET | `/api/health` | Health check |
| GET | `/api/health/detailed` | Detailed health check (per-subsystem status) |

## Code Conventions

- **Python**: PEP 8, type hints required
- **TypeScript**: Strict mode, ESLint rules
- **Commits**: Conventional commits (`feat:`, `fix:`, `refactor:`)
- **Comments**: English only, use `TODO:`, `FIXME:`, `HACK:`
- **Styling**: print-shop theme. Color tokens are CSS variables in
  `src/index.css`, mapped to Tailwind names (`paper`, `ink`, `rule`, `cyan`,
  `magenta`, `yellow`, `signal-*`) in `tailwind.config.cjs`; shared `tv-*`
  component classes (buttons, fields, sliders, segmented choices) live in the
  same stylesheet. Fonts are self-hosted with @fontsource (Archivo variable
  for text and display, DM Mono for values). Selected choices expose
  `aria-pressed`; sliders are named by their labels (`RangeField`).

## Testing

```bash
# Backend (~770 tests)
cd backend && pytest -v

# Frontend (Vitest, 27 test files)
npm test

# E2E (8 spec files, 49 tests)
npx playwright test
```

- E2E starts its own backend (port 8010, rate limits off via
  `RATE_LIMIT_ENABLED=false`) and Vite (port 5183), so it never reuses the dev
  servers. Override with `E2E_BACKEND_PORT` / `E2E_FRONTEND_PORT`.
- CI runs backend pytest, the frontend type check, Vitest, build, and E2E.
  Specs that need `backend/tests/fixtures/images-local/` skip without it.

- Unit tests: `backend/tests/unit/`
- Integration tests: `backend/tests/integration/`
- Performance tests: `backend/tests/performance/`
- Frontend tests: `src/**/*.test.{ts,tsx}`
- E2E tests: `e2e/*.spec.ts`

## Architecture Notes

### Color Processing Pipeline
1. Image upload → color extraction (K-means clustering)
2. Map colors to N configurable filament primaries
3. Calculate color mixing using `T_ch = 10^(-d / TD_ch)` and light-loss allocation
4. Generate layered output (STL/3MF) with greedy meshing optimization

Stack search (`compute_reference_matrices`) blends every ordered code on index
arrays in parallel and keeps one code per distinct 8-bit color (the first in
enumeration order), which matches exactly what matching every code returns.
Enumeration plus matching must fit `full_enumeration_budget_seconds`; over
budget, translucent sets use composition pruning and opaque sets are rejected,
as are pruned searches estimated over `stack_search_limit_seconds`.
`/api/v2/layer-limit` reports the largest layer count whose search fits
`layer_limit_budget_share` of that limit at `max_target_colors` targets, and the
layer slider stops there. Custom sets at that limit can keep millions of
distinct colors, so CIEDE2000 scoring runs in `DISTANCE_CHUNK` slices
(`core/color_materials.py`), the matrix cache is bounded by
`matrix_cache_max_references`, and mapping results are cached per reference
matrix so exports reuse the mapping processing computed.

Pixel-mode export and preview requests carry the model grid as a label map
(`services/label_map.py`, built by `src/utils/labelMap.ts`): block colors
plus one base64 byte per cell holding its block index, instead of per-pixel
coordinate lists (2M cells: ~2.7 MB instead of ~45 MB, and no per-pixel Python
objects). Internally, processing, previews and the STL/3MF generators work on
the label array; `block_box_runs` in `services/stl_generator.py` meshes and
extrudes each block's footprint for both generators within `stl_max_boxes`.
The process response still lists pixels per block for the browser. A 3MF holds
one object assembled from one part per filament, each with its filament color
as a 3MF material color (`services/threemf_writer.py`), so slicers load a
single object whose color layers stay in register.

Images larger than the model grid budget (`max_model_cells`, 4096 px per side)
are resampled at their physical size, snapping to whole detail-width cells when
resampling would land between half and one detail width. The browser applies
the same policy before upload (`src/utils/modelGrid.ts` mirrors
`image_processor.model_pitch`; the limits come from `/api/v2/filament-presets`),
and responses report the model pitch as `pixelSize`. Vectorized work uses the
thread count the startup probe found fastest (`core/parallel.py`).

### Telemetry
Production writes one JSON object per log line (`LOG_FORMAT=json`,
`config/logging_setup.py`), so `extra` fields become Railway log attributes.
`services/telemetry.emit` records named events: `api_request` (route template,
status, duration) for every API call, `api_error`, `image_processed`,
`model_exported`, `param_search_started`/`param_search_finished`,
`batch_processed`, and `bug_report_submitted`; counts since startup appear in
`/api/analytics`. The browser (`src/utils/telemetry.ts`) batches page views,
client errors, failed API responses (including edge failures the origin never
sees), user-visible errors, and funnel steps to `/api/events`, logged as
`client.<name>`. There are no cookies or stored IDs: a random ID groups one page
load, visitors are counted with a salted hash that rotates daily, and browsers
sending Global Privacy Control or Do Not Track send nothing. Event property
names must pass `ClientEvent` in `api/models.py`; one invalid event rejects its
whole batch. Railway log filters, for example:
`@event:image_processed AND @duration_ms:>10000`, `@event:client.api_failed`,
`@event:api_request AND @status:>=500`, `@level:error`.

### Key Patterns
- `FilamentConfigMixin` in `models.py` provides shared filament validation
- `@handle_api_errors` decorator in `error_handlers.py` standardizes error handling
- Handlers are `async`; CPU-heavy work (processing, previews, exports, batch)
  runs through `run_in_threadpool`, and large JSON responses are serialized in
  that thread with `api/responses.py`, so the single worker keeps serving
- Rate limiting via `slowapi` on all endpoints, keyed on the visitor address from
  `api/client_ip.py` (Railway's `X-Real-IP`; `CF-Connecting-IP` only from
  Cloudflare's published ranges)
- File validation (extension, size, magic bytes) in `validators.py`
- `Colors.from_configs()` creates N-color configurations from `ColorConfig` list

## Material Contract

`core/color_config.py` is the source of material presets. A material contains only
`name`, `hex`, and `transmission_distance` (a positive scalar or three positive
RGB values). A scalar is equivalent to three equal channel values. The browser
loads the catalog, print defaults, and TD transparency rule from
`/api/v2/filament-presets`; it has no separate built-in material table.

`config/print_defaults.py` defines regular color layers at 0.08 mm and
high-transmission color layers at 0.84 mm (three 0.28 mm slicer layers), with
three backing color layers. Pruning and the height default use the material
set's mean RGB TD against the threshold in `core/stack_prune.py`. The backing
mode selects actual light/dark material layers under common white illumination.

Parameter search returns every successful candidate in evaluation order,
including the current settings. Candidate IDs identify evaluations; users
choose previews without an automatic image-quality ranking.

Material measurements and photograph calibration belong to the research
repository. Production uses the material fields directly. Bambu and clear presets use
RGB-channel TD values; a custom material may use one TD or expand to RGB TD.

## Common Tasks

### Adding a new API endpoint
1. Define Pydantic models in `backend/api/models.py`
2. Create route handler in `backend/api/routes/`
3. Apply `@handle_api_errors("description")` decorator
4. Register route in `backend/main.py`

### Adding a frontend component
1. Create component in `src/components/`
2. Export from `src/components/index.ts`
3. Use in pages or other components
