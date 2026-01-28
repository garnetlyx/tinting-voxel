# img2stl

Transform images into physically accurate, multi-color 3D-printable STL files using CMYK color separation and optical color mixing (Beer-Lambert law).

## Features

- **Scientific Color Mixing** - Beer-Lambert optical model for accurate transparent filament color blending
- **CMYK Layer Generation** - Separate STL files for Cyan, Magenta, Yellow, White layers
- **Greedy Meshing Optimization** - 70-80% file size reduction vs naive pixel-to-box approach
- **Real-time Preview** - Side-by-side comparison of original vs processed image
- **Flexible Parameters** - Adjust maxColors, colorThreshold, layerHeight, pixelSize
- **Export Options** - ZIP download (4 STL files) + CSV color data export

## Tech Stack

- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS
- **Backend**: Python 3 + FastAPI + numpy-stl + PIL + scikit-learn

## Project Structure

```
img2stl/
├── backend/
│   ├── main.py                  # FastAPI application entry
│   ├── blend_color.py           # Core color algorithms
│   ├── api/
│   │   ├── models.py           # Pydantic data models
│   │   └── __init__.py
│   ├── services/
│   │   ├── image_processor.py  # Image processing service
│   │   ├── stl_generator.py    # STL generation service
│   │   ├── csv_generator.py    # CSV export service
│   │   └── __init__.py
│   └── requirements.txt
├── src/
│   ├── main.tsx                # React entry point
│   ├── image_to_stl_converter.tsx  # Main component
│   ├── api/
│   │   ├── client.ts           # API client
│   │   └── types.ts            # TypeScript types
│   └── index.css
├── vite.config.ts              # Vite config (includes API proxy)
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

**Method 1: Manual Start (Recommended)**

```bash
# Terminal 1: Start backend
cd backend
# Activate venv first!
uvicorn main:app --reload --port 8000

# Terminal 2: Start frontend
npm run dev
```

**Method 2: npm Scripts**

```bash
# Start frontend only
npm run dev

# Start backend only (macOS/Linux)
npm run dev:backend
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Usage

1. Upload an image (PNG, JPG)
2. Adjust parameters (optional):
   - **maxColors**: Number of colors to extract (1-20)
   - **colorThreshold**: Color merge sensitivity (0-100)
   - **layerHeight**: Layer thickness in mm (0.01-1.0)
   - **pixelSize**: Pixel physical size in mm (0.01-1.0)
3. Preview the processed image
4. Download STL ZIP or CSV data

## API Endpoints

### 1. POST /api/process-image
Process uploaded image and extract color blocks.

**Request**:
- `image`: File
- `maxColors`: int (default 10)
- `colorThreshold`: float (default 50)
- `pixelSize`: float (default 0.08)

### 2. POST /api/download-stl
Generate and download STL files.

**Request JSON**:
```json
{
  "colorBlocks": [...],
  "layerHeight": 0.08,
  "pixelSize": 0.08,
  "layerCount": 4,
  "imageDimensions": {"width": 208, "height": 208}
}
```

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
- [Project Instructions](CLAUDE.md)

## How It Works

1. **Color Extraction** - K-means clustering extracts dominant colors from image
2. **CMYK Mapping** - Colors mapped to CMYK primaries using LAB color space (perceptually uniform)
3. **Beer-Lambert Model** - Calculates light transmission through transparent layers
4. **STL Generation** - Creates layered 3D mesh with greedy meshing optimization

## License

ISC
