# img2stl - Project Instructions

## Overview

Image-to-STL color block converter that transforms images into layered 3D-printable STL files using CMYK color separation.

## Tech Stack

- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS
- **Backend**: Python 3 + FastAPI + numpy-stl + PIL + scikit-learn

## Project Structure

```
img2stl/
├── backend/              # Python FastAPI backend
│   ├── main.py           # Application entry point
│   ├── api/              # API routes and models
│   │   ├── models.py     # Pydantic data models
│   │   └── routes/       # Route handlers
│   ├── core/             # Core algorithms
│   │   └── blend_color.py  # Color blending (Beer-Lambert model)
│   ├── services/         # Business logic
│   │   ├── image_processor.py  # Image processing
│   │   ├── stl_generator.py    # STL file generation
│   │   ├── csv_generator.py    # CSV export
│   │   ├── mesh_optimizer.py   # Mesh optimization
│   │   └── vector_processor.py # Vector processing
│   ├── config/           # Configuration
│   └── tests/            # Test suite
├── src/                  # React frontend
│   ├── main.tsx          # Entry point
│   ├── pages/            # Page components
│   ├── components/       # UI components
│   ├── hooks/            # Custom hooks
│   └── api/              # API client
└── docs/                 # Documentation
```

## Development Commands

### Backend

```bash
cd backend
source .venv/bin/activate  # macOS/Linux
# .\.venv\Scripts\Activate.ps1  # Windows PowerShell

# Run server
uvicorn main:app --reload --port 8000

# Run tests
pytest

# Run specific test
pytest tests/unit/test_greedy_meshing.py -v
```

### Frontend

```bash
# Development server
npm run dev

# Build
npm run build

# Type check
npx tsc --noEmit
```

## Key URLs

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/process-image` | Process image and extract color blocks |
| POST | `/api/download-csv` | Download color data as CSV |
| POST | `/api/download-stl` | Generate and download STL ZIP |
| GET | `/api/health` | Health check |

## Code Conventions

- **Python**: PEP 8, type hints required
- **TypeScript**: Strict mode, ESLint rules
- **Commits**: Conventional commits (`feat:`, `fix:`, `refactor:`)
- **Comments**: English only, use `TODO:`, `FIXME:`, `HACK:`

## Testing

Backend tests use pytest:
- Unit tests: `backend/tests/unit/`
- Integration tests: `backend/tests/integration/`

Run all tests:
```bash
cd backend && pytest -v
```

## Architecture Notes

### Color Processing Pipeline
1. Image upload → color extraction (K-means clustering)
2. Map colors to CMYK primaries
3. Calculate color mixing using Beer-Lambert optical model
4. Generate layered STL files with greedy meshing optimization

### STL Generation
- Uses greedy meshing to reduce box count and file size
- Generates separate STL files for each CMYK layer
- Outputs as ZIP archive

## Common Tasks

### Adding a new API endpoint
1. Define Pydantic models in `backend/api/models.py`
2. Create route handler in `backend/api/routes/`
3. Register route in `backend/main.py`

### Adding a frontend component
1. Create component in `src/components/`
2. Export from `src/components/index.ts`
3. Use in pages or other components
