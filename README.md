# img2stl

Transform images into physically accurate, multi-color 3D-printable files using N-color filament separation and optical color mixing (Beer-Lambert law). Supports 4–16 configurable filament colors, STL/3MF/SVG output, batch processing, and an integrated calibration CLI.

## Features

- **Scientific Color Mixing** - Beer-Lambert optical model (hybrid per-channel-k) for accurate transparent filament color blending
- **N-Color Support (4–16 colors)** - Configurable filament primaries with custom hex values and per-color transmission/scattering parameters
- **Multiple Output Formats** - STL ZIP, SVG-STL, **3MF** (with named color objects), SVG-3MF, CSV, and slicer print-settings JSON
- **Batch Processing** - Process up to 20 images in one run
- **Palette Library** - 10 curated color palettes across 3 categories
- **3D WebGL Preview** - three.js render with orbit controls before export
- **Parameter Auto-Search** - Sweep maxColors / colorThreshold combinations and pick the best variant
- **Greedy Meshing Optimization** - 70-80% file size reduction vs naive pixel-to-box approach
- **Calibration CLI** - Optimize Beer-Lambert parameters against printed test plates (Phase 6/7 per-channel-k models)

## Tech Stack

- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS + three.js
- **Backend**: Python 3 + FastAPI + numpy-stl + PIL + scikit-learn + trimesh + lxml
- **Testing**: pytest (878 backend tests, 89% coverage), Vitest (frontend), Playwright (E2E)

## Project Structure

```
img2stl/
├── backend/
│   ├── main.py                  # FastAPI application entry
│   ├── core/                    # Core algorithms (blend_color, calibrator, presets)
│   ├── api/
│   │   ├── models.py            # Pydantic data models
│   │   ├── routes/              # Route handlers (image, download, batch, palette, ...)
│   │   └── __init__.py
│   ├── services/                # Business logic (image_processor, stl_generator, ...)
│   ├── config/                  # Settings, constants
│   ├── tools/calibration/       # Beer-Lambert calibration CLI
│   └── requirements.txt
├── src/                         # React frontend
│   ├── main.tsx                 # Entry point
│   ├── pages/Converter.tsx      # Main page component
│   ├── components/              # UI components
│   ├── hooks/                   # Custom hooks
│   ├── api/                     # API client + types
│   └── index.css
├── docs/                        # PRD, ARCHITECTURE
├── e2e/                         # Playwright E2E tests
├── vite.config.ts               # Vite config (includes API proxy)
├── package.json
└── index.html
```

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 18+

### Installation

```bash
# Clone repository
git clone https://github.com/garnetlyx/img2stl.git
cd img2stl

# Backend setup (Windows)
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Backend setup (macOS/Linux)
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend setup
cd ..
npm install
```

### Running

```bash
# One command to start both frontend and backend
npm run dev

# Or start separately
npm run dev:frontend  # Frontend only (port 5173)
npm run dev:backend   # Backend only (port 8000)
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Usage

1. Upload an image (PNG, JPG)
2. Optionally configure N-color filaments (presets or custom hex / k / td values)
3. Adjust processing parameters:
   - **maxColors**: Number of colors to extract (1-20)
   - **colorThreshold**: Color merge sensitivity (0-100)
   - **layerHeight**: Layer thickness in mm (0.01-1.0)
   - **pixelSize**: Pixel physical size in mm (0.01-1.0)
4. Preview the processed image and 3D WebGL render
5. Download STL ZIP / 3MF / SVG-STL / CSV / print-settings JSON

## API Endpoints

Full endpoint list (22 routes across V1, V2 N-color, batch, palette, param-search, health) is in [AGENTS.md](AGENTS.md). Highlights:

### V1 (legacy CMYK)

- `POST /api/process-image` — extract color blocks (pixel/SVG modes)
- `POST /api/simulate-preview` — simulated print preview (vector mode)
- `POST /api/download-csv` — color data CSV
- `POST /api/download-stl` — STL ZIP (default CMYK)
- `POST /api/download-svg-stl` — SVG-mode STL ZIP

### V2 (N-color)

- `POST /api/v2/download-stl` — N-color STL ZIP
- `POST /api/v2/download-svg-stl` — N-color SVG-mode STL
- `POST /api/v2/download-3mf` — 3MF with named color objects
- `POST /api/v2/download-svg-3mf` — SVG-mode 3MF
- `POST /api/v2/print-settings` — slicer print-settings JSON
- `GET  /api/v2/filament-presets` — available filament presets

Interactive OpenAPI docs at `/docs` when the backend is running.

## Troubleshooting

### 1. Backend Won't Start (`ModuleNotFoundError`)
Ensure your virtual environment is activated and dependencies are installed:
```bash
pip install -r requirements.txt
```

### 2. Frontend Can't Connect to Backend
- Check if backend is running at http://localhost:8000
- Verify Vite proxy in `vite.config.ts` matches backend port

### 3. Port Already in Use
Kill processes on port 8000 (backend) or 5173 (frontend):
```bash
# macOS/Linux
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9

# Windows
taskkill /PID <PID> /F
```

### 4. Windows Scripts Disabled
If you see "execution of scripts is disabled on this system":
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Development Tips

- **Cross-Platform**: React code uses `/` for paths. Python uses `pathlib` or `os.path.join`.
- **Hot Reload**: Both Vite (frontend) and Uvicorn (backend) support hot reload on file changes.
- **Docs**: Visit `/docs` on the backend for interactive OpenAPI documentation.

## Documentation

- [Product Requirements (PRD)](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Project Instructions](AGENTS.md)

## Calibration

The Beer-Lambert model uses two key parameters per filament:
- **alpha** -- absorption coefficient (`T = exp(-alpha * d / td)`)
- **td** -- transmission distance (material property)

These can be calibrated against photos of physical test prints to minimize perceptual color error (CIELAB Delta-E).

### Workflow

1. **Print a test plate** -- 16x16 grid of all 256 CMYW permutations
2. **Photograph** -- diffuse lighting, straight-on, crop to grid boundaries
3. **Run calibration** -- CLI optimizes parameters to match the photo

```bash
cd backend
source .venv/bin/activate

# Alpha-only (fast, recommended first step)
python -m tools.calibration.run_calibration \
  --photo tools/calibration/photos/print_regular_0.32.png \
  --preset bambu \
  --mode alpha \
  --gen-alpha 23

# Alpha + per-color td (slower, global optimizer)
python -m tools.calibration.run_calibration \
  --photo tools/calibration/photos/print_clear_3.36.png \
  --preset clear \
  --mode alpha_td
```

4. **Review output** -- `calibration_report.json` (metrics, per-color errors, worst codes) + `comparison.png` (3-panel: photo / original model / optimized model)
5. **Update presets** -- apply optimal values in `backend/core/color_config.py`

### CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--photo` | Path to calibration photo | (required) |
| `--preset` | `bambu` or `clear` | `bambu` |
| `--mode` | `alpha` (1 param, L-BFGS-B) or `alpha_td` (5 params, differential evolution) | `alpha` |
| `--gen-alpha` | Alpha used when generating the printed test plate | auto-detect |
| `--output` | Output directory | `tools/calibration/results/` |
| `--grid-size` | Grid dimensions | `16` |
| `--layer-height` | Layer height in mm | `0.08` |
| `--layer-count` | Number of layers | `4` |

See [`backend/tools/calibration/README.md`](backend/tools/calibration/README.md) for full details.

## How It Works

1. **Color Extraction** - K-means clustering extracts dominant colors from image (CIELAB distance, vectorized)
2. **N-Color Mapping** - Colors mapped to configured filament primaries using CIEDE2000 perceptual matching with hue preservation for dark chromatic colors
3. **Beer-Lambert Model** - Hybrid per-channel-k optical model calculates light transmission through transparent layers
4. **Mesh Generation** - Creates layered 3D mesh with greedy meshing optimization (70-80% box-count reduction)

## License

ISC
