# tinting-voxel - Project Instructions

## Overview

Image-to-STL/3MF color block converter that transforms images into layered 3D-printable files using CMYK color separation with Beer-Lambert optical modeling. Supports N-color filament configurations, batch processing, and multiple output formats.

## Tech Stack

- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS + three.js
- **Backend**: Python 3 + FastAPI + numpy-stl + PIL + scikit-learn + trimesh
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
│   │       ├── download.py   # V1 download endpoints (CSV, STL)
│   │       ├── download_v2.py # V2 N-color endpoints (STL, SVG-STL, 3MF, SVG-3MF, print settings)
│   │       ├── filament.py   # Filament preview
│   │       ├── batch.py      # Batch processing (up to 20 images)
│   │       ├── palette.py    # Palette library
│   │       ├── param_search.py # Param search SSE + top-N results
│   │       └── health.py     # Health check endpoints
│   ├── core/             # Core algorithms
│   │   ├── blend_color.py    # Color blending (Beer-Lambert model)
│   │   ├── blend_models.py   # Pluggable blend functions (hybrid per-channel-k)
│   │   ├── calibrator.py     # Beer-Lambert parameter calibration engine
│   │   ├── ramp_calibrator.py # Ramp plate calibration + per-color k optimizer
│   │   ├── calibration_priors.py # k-ordering constraints, TD1S priors
│   │   ├── code_grid.py      # Code grid generation utilities
│   │   ├── color_config.py   # Filament presets (single source of truth)
│   │   ├── color_materials.py # Material property definitions (k_rgb support)
│   │   ├── grid_sampling.py  # Photo sampling for calibration plates
│   │   ├── palette_library.py # Curated color palettes
│   │   ├── photo_preprocessor.py # Perspective correction, WB, glare masking
│   │   ├── plate_geometry.py # Plate geometry calculations
│   │   └── structured_plate.py # P1S 30x26 CMYWK structured plate layout
│   ├── services/         # Business logic
│   │   ├── analytics.py         # In-memory usage analytics
│   │   ├── batch_processor.py    # Multi-image batch processing
│   │   ├── csv_generator.py      # CSV export
│   │   ├── filament_preview.py   # Color matrix preview
│   │   ├── image_processor.py    # Image processing + auto-downscale
│   │   ├── matrix_cache.py       # Reference-matrix cache (powers /api/cache-stats)
│   │   ├── mesh_optimizer.py     # Greedy meshing optimization
│   │   ├── param_search_service.py # Auto parameter sweep engine
│   │   ├── print_settings_generator.py # Slicer settings JSON
│   │   ├── print_stack.py       # Print stack modeling
│   │   ├── raster_cleanup.py    # Raster post-processing cleanup
│   │   ├── stl_generator.py      # STL file generation
│   │   ├── svg_stl_generator.py  # SVG-mode STL generation
│   │   ├── threemf_generator.py  # 3MF output (trimesh+lxml)
│   │   └── vector_processor.py   # Vector/contour processing
│   ├── config/           # Configuration (settings, constants)
│   ├── tools/calibration/ # Calibration CLI (19+ scripts, photos, plates, results)
│   ├── scripts/          # Debug / one-off utility scripts
│   └── tests/            # Test suite (878 tests, 89% coverage)
│       ├── unit/             # Unit tests
│       ├── integration/      # Integration tests
│       ├── performance/      # Performance tests
│       ├── fixtures/
│       │   ├── images/        # Committed small test images (200-500px, <100KB)
│       │   └── images-local/  # Gitignored large images for local manual testing
│       └── test_calibration_qa.py # Calibration QA regression test
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
│   └── api/              # API client + types
├── e2e/                  # Playwright E2E tests (8 spec files, 45 tests)
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

### V1 (Legacy)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/process-image` | Process image (pixel/SVG modes) |
| POST | `/api/simulate-preview` | Simulated print preview (vector mode) |
| POST | `/api/download-csv` | Download color data as CSV |
| POST | `/api/download-stl` | Generate STL ZIP (default CMYK) |
| POST | `/api/download-svg-stl` | Generate SVG-mode STL ZIP |

### V2 (N-Color Support)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/download-stl` | STL ZIP with configurable colors |
| POST | `/api/v2/download-svg-stl` | SVG-mode STL with configurable colors |
| POST | `/api/v2/download-3mf` | 3MF file with named color objects |
| POST | `/api/v2/download-svg-3mf` | SVG-mode 3MF with configurable colors |
| POST | `/api/v2/print-settings` | JSON print settings for slicers |
| GET | `/api/v2/filament-presets` | List available filament presets |

### Other
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/filament-preview` | Color matrix preview |
| POST | `/api/batch/process` | Batch process up to 20 images |
| POST | `/api/batch/download-stl` | Batch STL download |
| POST | `/api/param-search` | Run parameter search, return top-N results |
| GET | `/api/param-search/progress/{job_id}` | SSE stream of search progress events |
| GET | `/api/palettes/` | List color palettes |
| GET | `/api/palettes/{id}` | Get specific palette |
| GET | `/api/analytics` | Usage analytics |
| GET | `/api/cache-stats` | Reference-matrix cache stats |
| GET | `/api/health` | Health check |
| GET | `/api/health/detailed` | Detailed health check (per-subsystem status) |

## Code Conventions

- **Python**: PEP 8, type hints required
- **TypeScript**: Strict mode, ESLint rules
- **Commits**: Conventional commits (`feat:`, `fix:`, `refactor:`)
- **Comments**: English only, use `TODO:`, `FIXME:`, `HACK:`

## Testing

```bash
# Backend (878 tests, 89% coverage)
cd backend && pytest -v

# Frontend (Vitest, 12 test files)
npm test

# E2E (8 spec files, 45 tests)
npx playwright test
```

- Unit tests: `backend/tests/unit/`
- Integration tests: `backend/tests/integration/`
- Performance tests: `backend/tests/performance/`
- Frontend tests: `src/**/*.test.{ts,tsx}`
- E2E tests: `e2e/*.spec.ts`

## Architecture Notes

### Color Processing Pipeline
1. Image upload → color extraction (K-means clustering)
2. Map colors to N configurable filament primaries
3. Calculate color mixing using Beer-Lambert optical model
4. Generate layered output (STL/3MF) with greedy meshing optimization

### Key Patterns
- `FilamentConfigMixin` in `models.py` provides shared filament validation
- `@handle_api_errors` decorator in `error_handlers.py` standardizes error handling
- Rate limiting via `slowapi` on all endpoints
- File validation (extension, size, magic bytes) in `validators.py`
- `Colors.from_configs()` creates N-color configurations from `ColorConfig` list

## Calibration

Internal CLI tool for optimizing Beer-Lambert model parameters (`alpha`, `td`) against photos of printed test plates. See [`backend/tools/calibration/README.md`](backend/tools/calibration/README.md) for full docs.

```bash
cd backend
source .venv/bin/activate

# Alpha-only calibration (fast, 1 parameter)
python -m tools.calibration.run_calibration \
  --photo tools/calibration/photos/print_regular_0.32.png \
  --preset bambu \
  --mode alpha \
  --gen-alpha 23

# Alpha + td calibration (slower, 5 parameters)
python -m tools.calibration.run_calibration \
  --photo tools/calibration/photos/print_clear_3.36.png \
  --preset clear \
  --mode alpha_td
```

Key parameters:
- `alpha` -- absorption coefficient in `T = exp(-alpha * d / td)`, default `12.0`
- `td` -- per-color transmission distance (material property)

Output: `calibration_report.json` + `comparison.png` (3-panel: photo / original / optimized)

## Research Data Conventions

### File naming (docs/research/)

- Photos: `<SAMPLE-ID>_<backing>_<seq>.JPG` (e.g., `PLATE-08-KX-A_white_01.JPG`). `seq` indexes the physical print, not repeat photos; a white/black pair of the same print shares `seq`.
- Sample IDs: `<PLATE-ID>-<PRINTER>-<rev>` (e.g., `PLATE-06-H2C-A`). Plate designs and physical prints are registered in `docs/research/SAMPLE_CATALOG.md` — add a registry row for every new print.
- Printer codes: `P1S` (Bambu P1S), `H2C` (Bambu H2C), `KX` (Anycubic Kobra X).
- Process-variant suffix (clear track): `_cross` = solid-infill rotation ON (crossed layers), `_aligned` = rotation OFF (parallel lines). Append before the extension, e.g. `PLATE-08-KX-A_white_01_cross.JPG`, `staircase-kx-ziro-b-cyan-1_cross.JPG`.
- ASCII only; hyphens/underscores as separators. Never use colons, spaces, or ad-hoc suffixes like ` copy` in tracked filenames (colons break Windows checkouts).

### Printers and process conditioning

- Opaque Bambu CMYK(WK) plates print on the H2C (Bambu Studio, 0.08 mm print layers; one 0.32 mm color layer = 4 print layers). Early experiments used the P1S.
- Transparent/clear filaments print on the Anycubic Kobra X — clear PLA is too brittle for the AMS feed path (Anycubic slicer, 0.28 mm print layers; one 0.84 mm color layer = 3 print layers).
- Archive the as-printed slicer project per print: `docs/research/plates/cmyk-blend-h2c.3mf` (H2C opaque), `docs/research/plates/cmyk_blend_clear-kx.3mf` (KX clear). If a setting changes between prints, save a new copy — do not overwrite the config a previous sample was printed with.
- Calibrated parameters (td/alpha/k presets) are **process-conditioned**: they are valid for the filament × printer × profile combination they were fitted on. The blend model consumes total stack thickness only; layer height, infill direction, and slicer differences are absorbed into the fitted parameters, so calibration prints and application prints must share the same profile (in particular: solid-infill rotation OFF / aligned lines for clear plates).

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