# ImageToSTLConverter - Setup Guide

## Project Overview

This is an image-to-STL color block converter that transforms images into layered 3D-printable STL files.

**Tech Stack**:
- Frontend: React 19 + TypeScript + Vite + Tailwind CSS
- Backend: Python 3 + FastAPI + numpy-stl + PIL + scikit-learn

## Architecture

```
src/
├── components/                  # UI components
│   ├── ErrorMessage.tsx        
│   ├── LoadingSpinner.tsx      
│   ├── ImageUploader.tsx       
│   ├── ParameterPanel.tsx      
│   ├── ImageComparison.tsx     
│   ├── ColorBlocksList.tsx     
│   ├── DownloadButtons.tsx     
│   └── index.ts                
│
├── pages/                       
│   └── Converter.tsx           
│
├── hooks/                       
│   └── useImageProcessor.ts    
│
├── api/                         
│   ├── client.ts
│   └── types.ts
│
├── config/                      
├── main.tsx                     
└── index.css      
```

### Frontend Responsibilities
- User interface
- Parameter adjustment (maxColors, colorThreshold, layerHeight, pixelSize)
- Image upload
- Real-time preview
- Display color block results
- Download STL ZIP and CSV files

### Backend Responsibilities
- Image processing and color extraction
- Color clustering (scikit-learn)
- Mapping to CMYK primary colors (map_to_nearest_color)
- Calculate color mixing using Beer-Lambert optical model
- Generate layered STL files
- Return processed preview image

## Prerequisites

### Windows
- Python 3.8+ ([Download](https://www.python.org/downloads/))
- Node.js 18+ ([Download](https://nodejs.org/))
- Git ([Download](https://git-scm.com/download/win))
- PowerShell or Command Prompt

### macOS
- Python 3.8+ (pre-installed or via [Homebrew](https://brew.sh/): `brew install python`)
- Node.js 18+ (via Homebrew: `brew install node` or [Download](https://nodejs.org/))
- Git (pre-installed with Xcode Command Line Tools)

## Initial Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd img2stl
```

### 2. Backend Setup

#### Windows (PowerShell)

```powershell
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

**Note**: If you get an execution policy error, run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Windows (Command Prompt)

```cmd
cd backend
python -m venv .venv
.\.venv\Scripts\activate.bat
pip install -r requirements.txt
```

#### macOS/Linux

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
# Navigate back to project root
cd ..

# Install Node dependencies
npm install
```

## Running the Application

### Method 1: Manual Start (Recommended)

#### Start Backend

**Windows (PowerShell):**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

**Windows (Command Prompt):**
```cmd
cd backend
.\.venv\Scripts\activate.bat
uvicorn main:app --reload --port 8000
```

**macOS/Linux:**
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

Backend will start at http://localhost:8000

#### Start Frontend (New Terminal)

```bash
# From project root
npm run dev
```

Frontend will start at http://localhost:5173

### Method 2: Using npm Scripts

```bash
# Start frontend only
npm run dev

# Start backend only (macOS/Linux)
npm run dev:backend
```

**Note**: You need to run frontend and backend in separate terminal windows.

## Verification

### Check Backend

Visit http://localhost:8000/docs to see the interactive API documentation.

### Check Frontend

Visit http://localhost:5173 to see the web interface.

## API Endpoints

### 1. POST /api/process-image
Process uploaded image and extract color blocks

**Request**:
- `image`: File (image file)
- `maxColors`: int (maximum number of colors, default 10)
- `colorThreshold`: float (color merge threshold, default 50)
- `pixelSize`: float (pixel size in mm, default 0.08)

**Response**:
```json
{
  "colorBlocks": [
    {
      "r": 128, "g": 64, "b": 200,
      "count": 1234,
      "pixels": [{"x": 10, "y": 20}, ...],
      "hex": "#8040c8"
    }
  ],
  "processedImage": "data:image/png;base64,...",
  "imageDimensions": {"width": 208, "height": 208}
}
```

### 2. POST /api/download-csv
Download color data as CSV

**Request**:
```json
{
  "colorBlocks": [...]
}
```

**Response**: CSV file

### 3. POST /api/download-stl
Generate and download STL files merged by primary colors

**Request**:
```json
{
  "colorBlocks": [...],
  "layerHeight": 0.08,
  "pixelSize": 0.08,
  "layerCount": 4,
  "imageDimensions": {"width": 208, "height": 208}
}
```

**Response**: ZIP file (containing CMYW_208x208x3.36_C.stl, etc.)

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

## Dependency Verification

### Backend Dependencies

**Windows:**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip list | findstr "fastapi uvicorn pillow scikit"
```

**macOS/Linux:**
```bash
cd backend
source .venv/bin/activate
pip list | grep -E "fastapi|uvicorn|pillow|scikit"
```

Expected packages:
- fastapi==0.121.2
- uvicorn==0.38.0
- pillow==12.0.0
- scikit-image==0.25.2
- scikit-learn==1.7.2

### Frontend Dependencies

```bash
npm list --depth=0
```

Expected packages:
- react@19.2.0
- vite@5.4.21
- typescript@5.9.3
- lucide-react@0.553.0

## Troubleshooting

### 1. Backend Won't Start

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:

**Windows:**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS/Linux:**
```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Frontend Can't Connect to Backend

**Error**: API requests fail

**Check**:
1. Is backend running? Visit http://localhost:8000/
2. Is Vite proxy configured correctly? (see vite.config.ts)

### 3. CORS Error

Ensure backend main.py CORS configuration includes frontend address:
```python
allow_origins=["http://localhost:5173", "http://localhost:3000"]
```

### 4. Python Virtual Environment Issues (Windows)

**Error**: `cannot be loaded because running scripts is disabled`

**Solution**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 5. Port Already in Use

**Backend (port 8000)**:
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:8000 | xargs kill -9
```

**Frontend (port 5173)**:
```bash
# Windows
netstat -ano | findstr :5173
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:5173 | xargs kill -9
```

## Development Notes

### Frontend Development
- Vite automatically proxies `/api/*` requests to `http://localhost:8000`
- Code changes trigger automatic hot reload
- TypeScript strict mode enabled

### Backend Development
- uvicorn `--reload` mode automatically restarts on code changes
- Logs output to console
- Interactive API docs: http://localhost:8000/docs

## Cross-Platform Development Tips

### Switching Between Windows and macOS

1. **Virtual Environment**: Always activate the appropriate virtual environment for your platform
2. **Git**: The `.venv` folder is already in `.gitignore`, so virtual environments won't be synced
3. **Dependencies**: Run `npm install` and `pip install -r requirements.txt` after pulling changes
4. **Line Endings**: Git should handle CRLF (Windows) vs LF (macOS/Linux) automatically

### Path Handling in Code

When writing code that handles file paths, use:
- Python: `pathlib.Path` or `os.path.join()`
- TypeScript/JavaScript: Always use forward slashes `/` (works on all platforms)

## Production Deployment (TODO)

- [ ] Docker containerization
- [ ] Cloud server deployment
- [ ] Environment variable configuration
- [ ] Production optimization
- [ ] Manual color mapping selection
- [ ] Async task processing (large image optimization)
- [ ] Caching mechanism (performance optimization)

## License

ISC
