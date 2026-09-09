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
│   │       ├── bug_report.py  # In-app bug reports (storage + optional email)
│   │       └── health.py     # Health check endpoints
│   ├── core/             # Core algorithms
│   │   ├── blend_color.py    # Color blending (Beer-Lambert model)
│   │   ├── blend_models.py   # Pluggable blend functions (hybrid per-channel-k)
│   │   ├── code_grid.py      # Code grid generation utilities
│   │   ├── color_config.py   # Filament presets (single source of truth)
│   │   ├── color_materials.py # Material property definitions (k_rgb support)
│   │   ├── grid_sampling.py  # Code-grid RGB assembly for blend fitting
│   │   └── palette_library.py # Supported filament palettes
│   ├── services/         # Business logic
│   │   ├── analytics.py         # In-memory usage analytics
│   │   ├── bug_report.py       # Bug report storage + optional email delivery
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
│   └── tests/            # Test suite (~680 tests)
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
│   ├── i18n/             # Locale runtime and feature translations (en, zh-CN)
│   └── api/              # API client + types
├── e2e/                  # Playwright E2E tests (7 spec files, 38 tests)
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
| POST | `/api/download-stl` | Generate STL ZIP (default Phase 6 CMYW) |
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
| POST | `/api/bug-report` | Submit in-app bug report (optional screenshot) |
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
# Backend (~680 tests)
cd backend && pytest -v

# Frontend (Vitest, 20 test files)
npm test

# E2E (7 spec files, 38 tests)
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

## Calibration & Research

Beer-Lambert parameter calibration (alpha/td/k fitting against printed test plates) is performed offline, outside this repo. This repo consumes calibration results only, as presets in `core/color_config.py`.

Calibrated parameters (td/alpha/k presets) are **process-conditioned**: they are valid for the filament × printer × profile combination they were fitted on, so calibration prints and application prints must share the same slicer profile.

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