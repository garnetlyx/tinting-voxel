# Architecture

**Last Updated**: 2026-01-27

## Overview

img2stl is a web application that converts images into layered 3D-printable STL files using CMYK color separation and optical physics-based color mixing. The system uses a client-server architecture with a React frontend and Python backend.

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
img2stl/
├── backend/                      # Python FastAPI backend
│   ├── main.py                   # Application entry, lifespan handler
│   ├── api/
│   │   ├── models.py             # Pydantic request/response schemas
│   │   └── routes/
│   │       ├── health.py         # Health check endpoint
│   │       ├── image.py          # /api/process-image
│   │       └── download.py       # /api/download-csv, /api/download-stl
│   ├── core/
│   │   └── blend_color.py        # Color classes, Beer-Lambert model (678 lines)
│   ├── services/
│   │   ├── image_processor.py    # K-means color extraction
│   │   ├── stl_generator.py      # STL file generation, color mapping
│   │   ├── mesh_optimizer.py     # Greedy meshing algorithm
│   │   ├── csv_generator.py      # CSV export
│   │   └── vector_processor.py   # Vector utilities
│   ├── config/
│   │   ├── settings.py           # Environment-based configuration
│   │   └── constants.py          # Application constants
│   ├── tests/
│   │   ├── unit/                 # Unit tests
│   │   └── integration/          # Integration tests
│   └── requirements.txt          # Python dependencies
│
├── src/                          # React frontend
│   ├── main.tsx                  # Application entry
│   ├── pages/
│   │   └── Converter.tsx         # Main converter page
│   ├── components/
│   │   ├── ImageUploader.tsx     # Drag-and-drop upload
│   │   ├── ParameterPanel.tsx    # Sliders for parameters
│   │   ├── ImageComparison.tsx   # Side-by-side preview
│   │   ├── ColorBlocksList.tsx   # Extracted colors display
│   │   ├── DownloadButtons.tsx   # CSV/STL download
│   │   ├── LoadingSpinner.tsx    # Loading state
│   │   ├── ErrorMessage.tsx      # Error display
│   │   └── index.ts              # Barrel exports
│   ├── hooks/
│   │   └── useImageProcessor.ts  # Processing logic and state
│   └── api/
│       ├── client.ts             # HTTP client functions
│       └── types.ts              # TypeScript interfaces
│
├── docs/                         # Documentation
│   ├── PRD.md                    # Product Requirements
│   └── ARCHITECTURE.md           # This file
│
├── vite.config.ts                # Vite config with API proxy
├── package.json                  # Node dependencies
├── tsconfig.json                 # TypeScript config
└── CLAUDE.md                     # Project instructions
```

## Core Components

### Backend Components

| Component | Responsibility | Key Dependencies |
|-----------|---------------|------------------|
| **main.py** | App initialization, CORS, route registration, lifespan events | FastAPI, uvicorn |
| **ImageProcessor** | K-means clustering, color extraction from uploaded images | scikit-learn, Pillow |
| **STLGenerator** | Convert color blocks to layered STL meshes, color mapping | numpy-stl, blend_color |
| **MeshOptimizer** | Greedy meshing to reduce box count, face culling | NumPy |
| **BlendColor (core)** | Beer-Lambert model, CMYK color mixing, LAB conversion | scikit-image, NumPy |

### Frontend Components

| Component | Responsibility | State Management |
|-----------|---------------|------------------|
| **Converter** | Main page layout, orchestrates child components | Props from useImageProcessor |
| **useImageProcessor** | All processing logic, API calls, state | React useState, useEffect |
| **ImageUploader** | File input, drag-and-drop handling | Local file state |
| **ParameterPanel** | Sliders for maxColors, threshold, layerHeight, pixelSize | Controlled inputs |
| **ImageComparison** | Side-by-side original vs processed display | Props only |
| **ColorBlocksList** | Display extracted color swatches with data | Props only |
| **DownloadButtons** | Trigger CSV/STL downloads | Loading state |

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
| **Color Space for Matching** | RGB Euclidean, HSV, LAB | LAB | Perceptually uniform; human vision aligns with LAB distance |
| **Color Mixing Model** | Simple averaging, Layer stacking, Beer-Lambert | Beer-Lambert | Physically accurate for transparent filaments |
| **Mesh Optimization** | None, Greedy meshing, Marching cubes | Greedy meshing | 70-80% reduction with simple implementation |
| **STL Format** | ASCII STL, Binary STL | Binary STL | 5x smaller files, faster parsing |
| **Separate vs Single STL** | Multi-color single file, Separate per color | Separate files | Slicer compatibility, manual filament swap support |
| **State Management** | Redux, Zustand, React hooks | Custom hook | Simpler for single-page app, no external dependencies |
| **API Communication** | REST, GraphQL, WebSocket | REST | Simple CRUD operations, stateless processing |
| **Reference Matrix Generation** | On-demand, Startup precompute | Startup precompute | Faster per-request processing, consistent results |

## Key Algorithms

### 1. Beer-Lambert Color Mixing

The Beer-Lambert law models light transmission through transparent layers:

```
T = e^(-α × d / td)

Where:
- T = transmission rate (0-1)
- α = absorption coefficient (default: 23)
- d = layer thickness (mm)
- td = transmission distance (material property)
```

Implementation in `blend_color.py:code_to_rgb()`:
1. Calculate transmission rate for each layer
2. Accumulate light loss through layers
3. Normalize and convert to RGB

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
