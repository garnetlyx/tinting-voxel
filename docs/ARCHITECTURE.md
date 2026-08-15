# Architecture

**Last Updated**: 2026-03-11

## Overview

tinting-voxel is a web application that converts images into layered 3D-printable STL files using CMYK color separation and optical physics-based color mixing. The system uses a client-server architecture with a React frontend and Python backend.

```
┌─────────────────────────────────────────────────────────────────────┐
│                           User Browser                              │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                     React Frontend                            │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │  │
│  │  │   Upload    │  │  Parameter  │  │   Preview/Download  │   │  │
│  │  │  Component  │  │    Panel    │  │     Components      │   │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘   │  │
│  │         │                │                     │              │  │
│  │         └────────────────┴─────────────────────┘              │  │
│  │                          │                                    │  │
│  │              ┌───────────┴───────────┐                        │  │
│  │              │   useImageProcessor   │                        │  │
│  │              │     (Custom Hook)     │                        │  │
│  │              └───────────┬───────────┘                        │  │
│  │                          │                                    │  │
│  │              ┌───────────┴───────────┐                        │  │
│  │              │      API Client       │                        │  │
│  │              └───────────┬───────────┘                        │  │
│  └──────────────────────────┼────────────────────────────────────┘  │
└─────────────────────────────┼───────────────────────────────────────┘
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                              │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      API Routes                               │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │  │
│  │  │ /process-    │  │ /download-   │  │   /download-     │    │  │
│  │  │   image      │  │    csv       │  │      stl         │    │  │
│  │  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘    │  │
│  └─────────┼─────────────────┼───────────────────┼──────────────┘  │
│            │                 │                   │                  │
│            ▼                 ▼                   ▼                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                       Services                               │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │   │
│  │  │ ImageProcessor │  │  CSVGenerator  │  │ STLGenerator  │  │   │
│  │  └────────┬───────┘  └────────────────┘  └───────┬───────┘  │   │
│  │           │                                      │           │   │
│  │           ▼                                      ▼           │   │
│  │  ┌────────────────┐                    ┌────────────────┐   │   │
│  │  │ Color Mapping  │                    │ MeshOptimizer  │   │   │
│  │  │ (K-means)      │                    │(Greedy Meshing)│   │   │
│  │  └────────────────┘                    └────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      Core Algorithms                         │   │
│  │                    (blend_color.py)                          │   │
│  │  ┌────────────────────────────────────────────────────────┐ │   │
│  │  │  Beer-Lambert Model  │  LAB Color Space  │  CMYK Map   │ │   │
│  │  └────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Frontend Framework** | React 19 + TypeScript | Type safety, component-based architecture, modern hooks API |
| **Build Tool** | Vite | Fast HMR, ESBuild-powered bundling, native ESM support |
| **Styling** | Tailwind CSS | Utility-first, rapid prototyping, small bundle size |
| **Backend Framework** | FastAPI | Async support, automatic OpenAPI docs, Pydantic validation |
| **Image Processing** | Pillow + scikit-learn | K-means clustering, image manipulation, battle-tested libraries |
| **Color Science** | scikit-image (rgb2lab) | Perceptually accurate LAB color space conversion |
| **STL Generation** | numpy-stl + custom | Binary STL output, mesh manipulation |
| **Data Processing** | NumPy + Pandas | Efficient matrix operations, color mapping tables |

## Directory Structure

```
tinting-voxel/
├── backend/              # Python FastAPI backend
│   ├── main.py           # Application entry point
│   ├── api/              # API routes and models
│   │   ├── models.py     # Pydantic data models (FilamentConfigMixin)
│   │   ├── error_handlers.py  # @handle_api_errors decorator
│   │   ├── validators.py # File upload validation
│   │   └── routes/       # Route handlers
│   │       ├── image.py      # Image processing (pixel/SVG modes)
│   │       ├── download.py   # V1 download endpoints (CSV, STL)
│   │       ├── download_v2.py # V2 N-color endpoints (STL, SVG-STL, 3MF, print settings)
│   │       ├── filament.py   # Filament preview
│   │       ├── batch.py      # Batch processing (up to 20 images)
│   │       ├── palette.py    # Palette library
│   │       └── health.py     # Health check endpoints
│   ├── core/             # Core algorithms
│   │   ├── blend_color.py        # Color blending (Original/Kromacut/Hybrid/Per-channel modes)
│   │   ├── blend_models.py       # Pluggable blend functions (hybrid_per_color_k, per_channel_k)
│   │   ├── calibrator.py         # Parameter calibration engine (16×16 plate)
│   │   ├── ramp_calibrator.py    # Ramp plate calibration + per-color k optimizer
│   │   ├── calibration_priors.py # k-ordering constraints, TD1S priors
│   │   ├── color_config.py       # Filament presets single source of truth (Phase6 preset)
│   │   ├── color_materials.py    # Material property definitions (k_rgb support)
│   │   ├── code_grid.py          # Code grid generation utilities
│   │   ├── grid_sampling.py      # Photo sampling for calibration plates
│   │   ├── plate_geometry.py     # Plate geometry calculations
│   │   ├── photo_preprocessor.py # Perspective correction, WB, glare masking
│   │   ├── structured_plate.py   # Structured plate layout (P1S 30×26 CMYWK)
│   │   └── palette_library.py    # Curated color palettes
│   ├── services/         # Business logic
│   │   ├── image_processor.py    # Image processing + auto-downscale
│   │   ├── stl_generator.py      # STL file generation
│   │   ├── svg_stl_generator.py  # SVG-mode STL generation
│   │   ├── threemf_generator.py  # 3MF output (trimesh+lxml)
│   │   ├── csv_generator.py      # CSV export
│   │   ├── mesh_optimizer.py     # Greedy meshing optimization
│   │   ├── vector_processor.py   # Vector/contour processing
│   │   ├── batch_processor.py    # Multi-image batch processing
│   │   ├── filament_preview.py   # Color matrix preview
│   │   ├── print_settings_generator.py # Slicer settings JSON
│   │   └── analytics.py         # In-memory usage analytics
│   ├── tools/           # CLI tools
│   │   └── calibration/ # Calibration tools (19 CLI scripts)
│   │       ├── generate_plate.py            # 16×16 permutation plate
│   │       ├── generate_ramp.py             # Single-color 4×5 ramp
│   │       ├── generate_multicolor_ramp.py  # Multi-color 12×5 ramp
│   │       ├── generate_pair_ramp.py        # Two-color 12×4 ramp
│   │       ├── generate_structured_plate.py # P1S 30×26 CMYWK structured plate
│   │       ├── run_calibration.py           # 16×16 plate calibration
│   │       ├── run_ramp_calibration.py      # Ramp plate calibration
│   │       ├── run_structured_calibration.py # Whole-plate B/W backing calibration
│   │       ├── run_cross_validation.py      # All param sets × all photos
│   │       ├── run_model_search.py          # New model family exploration
│   │       └── ...                          # Additional diagnostic + utility scripts
│   ├── config/           # Configuration
│   └── tests/            # Test suite (878 tests, 89% coverage)
│       └── fixtures/
│           ├── images/        # Committed small test images (200-500px, <100KB)
│           └── images-local/  # Gitignored large images for local manual testing
│       └── calibration/      # Calibration photos, CLI runner, results
├── src/                  # React frontend
│   ├── main.tsx          # Entry point
│   ├── pages/            # Page components
│   ├── components/       # UI components (25+ components)
│   │   ├── ThreeDPreview.tsx     # WebGL 3D preview (three.js)
│   │   ├── BatchProcessor.tsx    # Batch image processing UI
│   │   ├── PaletteLibrary.tsx    # Palette selection UI
│   │   ├── FilamentConfigPanel.tsx # N-color filament config
│   │   ├── ImageEditor.tsx       # Canvas crop/resize editor
│   │   └── UploadDropzone.tsx    # Drag-and-drop upload
│   ├── hooks/            # Custom hooks
│   └── api/              # API client + types
├── e2e/                  # Playwright E2E tests (8 spec files, 45 tests)
├── Dockerfile            # Multi-stage Docker build
├── docker-compose.yml    # Docker Compose config
├── fly.toml              # Fly.io deploy config
└── railway.toml          # Railway deploy config
```

## Core Components

### Backend Components

| Component | Responsibility | Key Dependencies |
|-----------|---------------|------------------|
| **main.py** | App initialization, CORS, route registration, lifespan events | FastAPI, uvicorn |
| **ImageProcessor** | K-means clustering, color extraction from uploaded images | scikit-learn, Pillow |
| **STLGenerator** | Convert color blocks to layered STL meshes, color mapping | numpy-stl, blend_color |
| **SVG-STLGenerator** | Vector-based STL generation from SVG contours | numpy-stl, svg.path |
| **3MFGenerator** | 3MF file generation with named color objects | trimesh, lxml |
| **MeshOptimizer** | Greedy meshing to reduce box count, face culling | NumPy |
| **BlendColor (core)** | Color blending (Original/Hybrid/per-color-k modes), CIEDE2000 matching | scikit-image, NumPy |
| **BlendModels** | Pluggable blend functions (hybrid_per_color_k, hybrid_per_channel_k) | NumPy |
| **ColorConfig** | Filament presets (BAMBU_CMYK_PHASE6_PRESET with per-color k) | dataclasses |
| **Calibrator** | 16×16 plate calibration, per-color k support | scipy.optimize, PIL |
| **RampCalibrator** | Ramp plate calibration, k_rgb optimizer, k-ordering constraints | scipy.optimize |
| **CalibrationPriors** | k-ordering penalty (K>W>M>C>Y), TD1S prior | NumPy |
| **FilamentPreview** | Color matrix preview generation | PIL, NumPy |
| **BatchProcessor** | Multi-image batch processing | concurrent.futures |
| **PaletteLibrary** | Curated color palette management | dataclasses |
| **PrintSettingsGenerator** | Slicer settings JSON export | json |
| **Analytics** | In-memory usage analytics | threading |

### Frontend Components

| Component | Responsibility | State Management |
|-----------|---------------|------------------|
| **Converter** | Main page layout, orchestrates child components | Props from useImageProcessor |
| **useImageProcessor** | All processing logic, API calls, state | React useState, useEffect |
| **UploadDropzone** | Drag-and-drop file upload with preview | Local file state |
| **ParameterPanel** | Sliders for maxColors, threshold, layerHeight, pixelSize | Controlled inputs |
| **FilamentConfigPanel** | N-color filament configuration UI | Local state, preset manager |
| **ThreeDPreview** | WebGL 3D preview with orbit controls | Three.js, useRef |
| **BatchProcessor** | Batch image processing UI | Local file state |
| **PaletteLibrary** | Color palette selection UI | Local filter state |
| **ImageEditor** | Canvas-based crop/resize editor | Canvas API, useRef |
| **ColorBlocksList** | Display extracted color swatches with data | Props only |
| **DownloadButtons** | Trigger CSV/STL/3MF downloads | Loading state |

## Data Flow

### Image Processing Flow

```
1. User Upload
   ┌──────────────┐
   │ Image File   │
   │ (PNG/JPG)    │
   └──────┬───────┘
          │
          ▼
2. Frontend Conversion
   ┌──────────────┐
   │ Canvas API   │──► Blob/File object
   └──────┬───────┘
          │
          ▼
3. Backend Processing
   ┌──────────────────────────────────────────────────────────┐
   │                                                          │
   │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
   │  │ Resize &    │───►│  K-means    │───►│ Map to CMYK │  │
   │  │ Normalize   │    │ Clustering  │    │ Primaries   │  │
   │  └─────────────┘    └─────────────┘    └─────────────┘  │
   │                                                          │
   └──────────────────────────┬───────────────────────────────┘
                              │
                              ▼
4. Response
   ┌──────────────────────────────────────────────────────────┐
   │ {                                                         │
   │   colorBlocks: [{ r, g, b, count, pixels, hex }, ...],   │
   │   processedImage: "data:image/png;base64,...",           │
   │   imageDimensions: { width, height }                     │
   │ }                                                         │
   └──────────────────────────────────────────────────────────┘
```

### STL Generation Flow

```
1. Input: colorBlocks + parameters
   ┌────────────────────────────────────────────┐
   │ colorBlocks: [{ r, g, b, pixels }, ...]    │
   │ layerHeight: 0.08mm                        │
   │ pixelSize: 0.08mm                          │
   │ layerCount: 4                              │
   └──────────────────┬─────────────────────────┘
                      │
                      ▼
2. Color Mapping (Beer-Lambert)
   ┌────────────────────────────────────────────┐
   │ Input RGB → LAB Space → Find nearest CMYK  │
   │                                            │
   │ Reference Matrix (256 combinations):       │
   │   CCCC, CCCM, CCCY, CCCW, ...             │
   │   Each with pre-computed RGB value         │
   └──────────────────┬─────────────────────────┘
                      │
                      ▼
3. Mesh Generation (per layer)
   ┌────────────────────────────────────────────┐
   │ For each color block:                      │
   │   For each layer (C, M, Y, W):             │
   │     ┌─────────────────────────────────┐    │
   │     │ Greedy Meshing:                 │    │
   │     │ pixels → grid → rectangles     │    │
   │     │ (70-80% box reduction)         │    │
   │     └─────────────────────────────────┘    │
   └──────────────────┬─────────────────────────┘
                      │
                      ▼
4. Output: ZIP with 4 STL files
   ┌────────────────────────────────────────────┐
   │ CMYW_208x208x0.32_C.stl  (Cyan layer)      │
   │ CMYW_208x208x0.32_M.stl  (Magenta layer)   │
   │ CMYW_208x208x0.32_Y.stl  (Yellow layer)    │
   │ CMYW_208x208x0.32_W.stl  (White layer)     │
   └────────────────────────────────────────────┘
```

## API Design

### Endpoints

| Endpoint | Method | Input | Output |
|----------|--------|-------|--------|
| `/api/process-image` | POST | `multipart/form-data` (image + params) | JSON (colorBlocks, processedImage) |
| `/api/download-csv` | POST | JSON (colorBlocks) | `text/csv` file |
| `/api/download-stl` | POST | JSON (colorBlocks, params) | `application/zip` file |
| `/api/health` | GET | None | JSON (status, version) |

### Request/Response Models

```python
# Image Processing Request (Form Data)
- image: File (required)
- maxColors: int = 10
- colorThreshold: float = 50.0
- pixelSize: float = 0.08

# Image Processing Response
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

# STL Download Request
{
  "colorBlocks": [...],
  "layerHeight": 0.08,
  "pixelSize": 0.08,
  "layerCount": 4,
  "imageDimensions": {"width": 208, "height": 208}
}
```

## Design Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| **Color Space for Matching** | RGB Euclidean, HSV, LAB Euclidean, CIEDE2000 | CIEDE2000 | Perceptually uniform + hue weighting for dark chromatic colors |
| **Color Mixing Model** | Beer-Lambert scalar, Hybrid per-color k, Full K-M | Hybrid per-color k | Per-color scattering + absorption; generalizes to arbitrary filaments |
| **Mesh Optimization** | None, Greedy meshing, Marching cubes | Greedy meshing | 70-80% reduction with simple implementation |
| **STL Format** | ASCII STL, Binary STL | Binary STL | 5x smaller files, faster parsing |
| **Separate vs Single STL** | Multi-color single file, Separate per color | Separate files | Slicer compatibility, manual filament swap support |
| **State Management** | Redux, Zustand, React hooks | Custom hook | Simpler for single-page app, no external dependencies |
| **API Communication** | REST, GraphQL, WebSocket | REST | Simple CRUD operations, stateless processing |
| **Reference Matrix Generation** | On-demand, Startup precompute | Startup precompute | Faster per-request processing, consistent results |

## Key Algorithms

### 1. Hybrid Per-Color k Color Mixing

The production color mixing model uses a hybrid Beer-Lambert formula with per-color scattering coefficients (simplified Kubelka-Munk):

```
T_ch(c) = exp(-(scatter_alpha / td_c  +  k_c × A_ch(c)) × d)

Where:
- T_ch    = per-channel transmission
- scatter_alpha / td_c = base scattering (channel-neutral, handles White/Black)
- k_c     = per-color scattering coefficient (Phase 6 calibrated)
- A_ch(c) = per-channel absorption from filament hex color
- d       = layer height (mm)
```

Phase 6 calibrated k values (K > W > M > C > Y physical ordering):

| Color | k | td (TD1S-mapped) |
|-------|---|---|
| K (Black) | 17.65 | 2.21 |
| W (White) | 12.39 | 5.48 |
| M (Magenta) | 8.42 | 2.22 |
| C (Cyan) | 8.13 | 1.70 |
| Y (Yellow) | 3.73 | 4.15 |

Implementation: `blend_models.py:blend_hybrid_per_color_k()`, preset: `BAMBU_CMYK_PHASE6_PRESET`.

### 2. Greedy Meshing

Reduces STL file size by merging adjacent pixels into larger rectangles:

```
Input Grid:        Output Rectangles:
1 1 1 0 0          ┌─────┐
1 1 1 0 0    →     │  A  │   A: (0,0) 3x3
1 1 1 0 0          │     │   B: (3,2) 2x2
0 0 0 1 1          └─────┘
0 0 0 1 1                ┌───┐
                         │ B │
                         └───┘

9 pixels → 2 boxes (78% reduction)
```

Implementation in `mesh_optimizer.py:greedy_mesh_2d()`:
1. Convert pixels to boolean grid
2. Scan left-to-right, top-to-bottom
3. For each unprocessed pixel, find max rectangle
4. Mark rectangle as processed, continue

### 3. K-Means Color Clustering

Groups similar colors using scikit-learn's MiniBatchKMeans:

```python
# Simplified flow
1. Extract all pixel RGB values
2. Normalize to [0, 1]
3. Run K-means with n_clusters=maxColors
4. Group pixels by cluster assignment
5. Calculate cluster center as representative color
```

## Performance Considerations

| Aspect | Approach | Target |
|--------|----------|--------|
| **Image Processing** | In-memory PIL operations | < 5s for 512x512 |
| **Color Mapping** | Pre-computed 256-entry lookup table | O(n) per color |
| **Mesh Generation** | NumPy vectorized operations | < 10s for 256x256 |
| **File Size** | Greedy meshing + binary STL | 70-80% reduction |
| **Concurrent Requests** | Stateless design, no shared mutable state | Scale horizontally |

## Security Considerations

- **File Validation**: Magic number check for image formats
- **Size Limits**: 10MB max upload, 1024x1024 max dimensions
- **Input Sanitization**: Pydantic validation on all parameters
- **CORS**: Restricted to configured origins
- **No Persistence**: All files processed in-memory, cleaned immediately

## Future Architecture Considerations

1. **GPU Acceleration**: Port K-means to cuML for faster clustering
2. **WebAssembly**: Client-side Beer-Lambert calculations
3. **Task Queue**: Celery/Redis for large image async processing
4. **Caching**: Redis cache for repeated color mappings
5. **CDN**: Static asset delivery for frontend
