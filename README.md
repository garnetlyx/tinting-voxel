# tinting-voxel

Transform images into physically accurate, multi-color 3D-printable files using N-color filament separation and optical color mixing (Beer-Lambert law). Supports 4–16 configurable filament colors, STL/3MF/SVG output, batch processing, and parameter auto-search.

## Features

- **Optical Color Mixing** - One transmission formula for every filament: `T_ch = 10^(-d / TD_ch)`, composed by light-loss allocation using the filament hex color
- **N-Color Support (4–16 colors)** - Arbitrary color codes with custom hex values and a single transmission-distance field, accepting one number or three RGB values
- **Multiple Output Formats** - STL ZIP, SVG-STL, **3MF** (one object with a named, colored part per filament), SVG-3MF, CSV, and slicer print-settings JSON
- **Batch Processing** - Process up to 20 images in one run
- **Palette Library** - Four built-in filament configurations supplied by the backend catalog
- **Interface Languages** - English and Simplified Chinese with automatic detection, persistent switching, and feature-based translation resources
- **Bug Reports** - In-app feedback with optional page screenshots, conversion settings, and diagnostic logs
- **3D WebGL Preview** - three.js render with orbit controls before export
- **Parameter Auto-Search** - Scores the current settings and a pattern search over the mode's settings by mean CIEDE2000 against the image; previews rank closest first as they finish, and choosing one applies it
- **Greedy Meshing Optimization** - 70-80% file size reduction vs naive pixel-to-box approach

## Tech Stack

- **Frontend**: React 19 + TypeScript + Vite + build-time Tailwind CSS + three.js
- **Backend**: Python 3 + FastAPI + numpy-stl + PIL + scikit-learn
- **Testing**: pytest (~700 backend tests), Vitest (frontend), Playwright (E2E)

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
│   ├── i18n/                    # Frontend locale runtime and feature translations
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
2. Choose Bambu CMYWK (default), Bambu CMYW, Clear CMYG, or Clear CMYW. Custom filaments need a hex color and one TD value; expand TD to enter separate R, G, and B values.
3. Adjust processing parameters:
   - **maxColors**: Number of colors to extract (1-20)
   - **colorThreshold**: Color merge sensitivity (0-100)
   - **layerHeight**: Thickness of one color layer: 0.08 mm for regular materials; 0.84 mm for high-transmission materials (three 0.28 mm slicer layers)
   - **Backing**: Three backing color layers by default; choose the lightest or darkest available material
   - **pixelSize**: Pixel physical size in mm (0.01-1.0)
4. Preview the processed image and 3D WebGL render
5. Download STL ZIP / 3MF / SVG-STL / CSV / print-settings JSON

## API Endpoints

The full endpoint list is in [AGENTS.md](AGENTS.md). Highlights:

### Image Processing and CSV

- `POST /api/process-image` — extract color blocks (pixel/SVG modes)
- `POST /api/simulate-preview` — simulated print preview (vector mode)
- `POST /api/download-csv` — color data CSV

### V2 (N-color)

- `POST /api/v2/download-stl` — N-color STL ZIP
- `POST /api/v2/download-svg-stl` — N-color SVG-mode STL
- `POST /api/v2/download-3mf` — 3MF: one object with a named, colored part per filament
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
- **Localization**: Add languages through `src/i18n/`; see the [presentation-layer boundary](docs/ARCHITECTURE.md#frontend-localization-boundary). UI language never changes calculation or export data.
- **Docs**: Visit `/docs` on the backend for interactive OpenAPI documentation.

## Documentation

- [Product Requirements (PRD)](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Project Instructions](AGENTS.md)

## Material Properties and Research

`backend/core/color_config.py` owns the built-in material catalog. Each material
contains `name`, `hex`, and `transmission_distance`: a positive number in mm or
three positive numbers in RGB order. A single value applies equally to all three
channels. All built-in presets contain channel-specific TD values. Bambu CMYW/CMYWK
share the effective RGB TD estimates from the existing Bambu staircase photographs
(`tinting-voxel-research/data/results/bambu-cmywk-td-recovery/`).
Photo-specific calibration terms stay in the research analysis.

Production uses these material values directly. Photograph exposure, white-balance
adjustments, and fitted capture corrections belong to the companion research
repository and are not product material inputs.

The related measurement and modeling research is published as:

> Garnet Liu. *Predicting Stacked-Filament Color from Independently Measured Filament Properties.* EngXiv preprint, September 2026. [doi:10.31224/7794](https://doi.org/10.31224/7794) (CC BY 4.0)

## How It Works

1. **Color Extraction** - K-means clustering extracts dominant colors from image (CIELAB distance, vectorized)
2. **N-Color Mapping** - Colors mapped to configured filament primaries using CIEDE2000 perceptual matching with hue preservation for dark chromatic colors
3. **Beer-Lambert Model** - `T_ch = 10^(-d / TD_ch)` calculates each layer’s transmission; the same stacking rule applies to every material
4. **Mesh Generation** - Creates layered 3D mesh with greedy meshing optimization (70-80% box-count reduction)

## License

Apache-2.0. See [LICENSE](LICENSE).
