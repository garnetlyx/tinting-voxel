# tinting-voxel

Transform images into physically accurate, multi-color 3D-printable files using N-color filament separation and optical color mixing (Beer-Lambert law). Supports 4–16 configurable filament colors, STL/3MF/SVG output, batch processing, and parameter auto-search.

## Features

- **Scientific Color Mixing** - Beer-Lambert optical model (hybrid per-channel-k) for accurate transparent filament color blending
- **N-Color Support (4–16 colors)** - Configurable filament primaries with custom hex values and per-color transmission/scattering parameters
- **Multiple Output Formats** - STL ZIP, SVG-STL, **3MF** (with named color objects), SVG-3MF, CSV, and slicer print-settings JSON
- **Batch Processing** - Process up to 20 images in one run
- **Palette Library** - 10 curated color palettes across 3 categories
- **Bug Reports** - In-app feedback with optional page screenshots, conversion settings, and diagnostic logs
- **3D WebGL Preview** - three.js render with orbit controls before export
- **Parameter Auto-Search** - Sweep maxColors / colorThreshold combinations and pick the best variant
- **Greedy Meshing Optimization** - 70-80% file size reduction vs naive pixel-to-box approach
- **Research-Backed Parameters** - Beer-Lambert parameters fitted against photos of printed test plates

## Tech Stack

- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS + three.js
- **Backend**: Python 3 + FastAPI + numpy-stl + PIL + scikit-learn + trimesh + lxml
- **Testing**: pytest (~670 backend tests), Vitest (frontend), Playwright (E2E)

## Project Structure

```
tinting-voxel/
├── backend/
│   ├── main.py                  # FastAPI application entry
│   ├── core/                    # Core algorithms (blend_color, presets, code grid)
│   ├── api/
│   │   ├── models.py            # Pydantic data models
│   │   ├── routes/              # Route handlers (image, download, batch, palette, ...)
│   │   └── __init__.py
│   ├── services/                # Business logic (image_processor, stl_generator, ...)
│   ├── config/                  # Settings, constants
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
git clone https://github.com/garnetlyx/tinting-voxel.git
cd tinting-voxel

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

## Bug Reports

Use the bug button at the bottom right to send a report. A description is optional;
browser details, current conversion settings, and recent errors are included.
Screenshots are opt-in and include only the current page view (including any visible
uploaded image and 3D preview), excluding the report dialog.

`POST /api/bug-report` accepts a description (up to 1,000 characters), a bounded
`frontendContext`, and an optional PNG/JPEG data URL (up to 5 MB). Requests are limited
to 6 MB and three submissions per hour per client IP, using the existing API limiter.
The response contains `success`, `reportId`, and `delivery` (`stored` or `email`).

Reports are saved as private JSON files under `BUG_REPORT_STORAGE_DIR` (default:
`bug-reports/`, relative to the backend working directory). A report is acknowledged
only after its file has been written. Configure a **persistent directory outside
`static/`** in production and manage its retention and backups; ephemeral disks will
lose reports on redeployment. The directory is not served by the application.

To also receive email, set these **backend-only** environment variables:

- `RESEND_API_KEY`: your Resend API key.
- `RESEND_FROM`: a sender on your verified Resend domain.
- `BUG_REPORT_EMAIL_TO`: the recipient inbox.

These are the same email settings used by `ai-judge`. Emails include the description,
converter/browser details, up to 50 recent application log lines, and the optional
screenshot attachment. Failed or unconfigured email delivery leaves the saved report
available locally. Common credential patterns, URL query strings,
and image payloads are filtered from automatic diagnostics; the original image is
not collected unless it is visible in a screenshot the user selects.

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
- [Blend Functions](docs/BLEND_FUNCTIONS.md)
- [Project Instructions](AGENTS.md)

## Calibration

Beer-Lambert parameters (`alpha`, `td`, per-color `k`) in the filament presets are fitted offline against photos of printed test plates. Fitted values are promoted into presets in `backend/core/color_config.py` here.

## How It Works

1. **Color Extraction** - K-means clustering extracts dominant colors from image (CIELAB distance, vectorized)
2. **N-Color Mapping** - Colors mapped to configured filament primaries using CIEDE2000 perceptual matching with hue preservation for dark chromatic colors
3. **Beer-Lambert Model** - Hybrid per-channel-k optical model calculates light transmission through transparent layers
4. **Mesh Generation** - Creates layered 3D mesh with greedy meshing optimization (70-80% box-count reduction)

## License

Apache-2.0. See [LICENSE](LICENSE).
