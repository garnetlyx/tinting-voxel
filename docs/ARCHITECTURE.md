# Architecture

**Last Updated**: 2026-09-09

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
| **Frontend Localization** | i18next + react-i18next | Typed feature namespaces, live locale switching, English fallback |
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
│   │       ├── param_search.py # Param search SSE + top-N results
│   │       ├── bug_report.py  # In-app bug reports
│   │       └── health.py     # Health check endpoints
│   ├── core/             # Core algorithms
│   │   ├── blend_color.py        # Color blending (BlendTestGenerator, colors_key)
│   │   ├── blend_models.py       # The unified blend formula + vectorized batch path
│   │   ├── color_config.py       # Filament presets single source of truth (Phase6 preset)
│   │   ├── color_materials.py    # Material property definitions (k_rgb support)
│   │   ├── code_grid.py          # Code grid generation utilities
│   │   ├── grid_sampling.py      # Code-grid RGB assembly for blend fitting
│   │   ├── plate_geometry.py     # Plate geometry calculations
│   │   └── palette_library.py    # Supported filament palettes
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
│   │   ├── print_stack.py       # Print stack modeling
│   │   ├── raster_cleanup.py    # Raster post-processing cleanup
│   │   ├── matrix_cache.py      # Reference-matrix cache (powers /api/cache-stats)
│   │   ├── param_search_service.py # Auto parameter sweep engine
│   │   ├── bug_report.py        # Bug report storage + optional email delivery
│   │   └── analytics.py         # In-memory usage analytics
│   ├── config/           # Configuration
│   └── tests/            # Test suite (~680 tests)
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
│   │   ├── ImageEditor.tsx       # Canvas crop/resize editor
│   │   └── UploadDropzone.tsx    # Drag-and-drop upload
│   ├── i18n/             # Locale runtime, typed resources, presentation adapters
│   │   └── locales/      # en/ and zh-CN/ feature namespaces
│   ├── hooks/            # Custom hooks
│   └── api/              # API client + types
├── e2e/                  # Playwright E2E tests (7 spec files, 38 tests)
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
| **BlendColor (core)** | BlendTestGenerator, colors_key, CIEDE2000 matching | scikit-image, NumPy |
| **BlendModels** | The unified formula (mu_ch = ln10/td + k*A_ch) and its vectorized batch | NumPy |
| **ColorConfig** | Filament presets (BAMBU_CMYW_PHASE6_PRESET with per-color k) | dataclasses |
| **FilamentPreview** | Color matrix preview generation | PIL, NumPy |
| **BatchProcessor** | Multi-image batch processing | concurrent.futures |
| **PaletteLibrary** | Curated color palette management | dataclasses |
| **PrintSettingsGenerator** | Slicer settings JSON export | json |
| **Analytics** | In-memory usage analytics | threading |
| **BugReportService** | Bug report storage + optional email delivery | json, Resend API |

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
| **PaletteLibrary** | Color palette selection UI | Local expanded/loading state |
| **ImageEditor** | Canvas-based crop/resize editor | Canvas API, useRef |
| **ColorBlocksList** | Display extracted color swatches with data | Props only |
| **DownloadButtons** | Trigger CSV/STL/3MF downloads | Loading state |
| **LanguageSelector** | Switch the workspace language | Dedicated locale preference |

### Frontend Styles and Brand Assets

Vite builds Tailwind v3 through PostCSS using `tailwind.config.cjs` and
`postcss.config.cjs`. Content scanning covers `index.html` and `src/`; UI classes
must be complete strings so the build can discover them. `src/index.css` contains
the Tailwind layers and base typography. The browser loads only the bundled CSS.

`public/brand.svg` is the shared header/favicon artwork. The ICO contains 16, 32,
and 48 px versions; the Apple Touch Icon is an opaque 180 px PNG. These raster
icons are exports of the same SVG. `public/share-card.svg` is the editable source
for the 1200 × 630 PNG used by social previews. Keep exported files synchronized
when changing their source artwork. Vite copies `public/` into the build, and the
Docker frontend stage includes both the assets and CSS configuration files.

`index.html` contains the canonical production URL, default English description,
Open Graph metadata, icon links, and sharing image URLs. They are available in
the initial response without executing JavaScript. UI locale changes synchronize
the document title and description; the single canonical URL uses one English
sharing card.

### Frontend Localization Boundary

Localization is owned by the presentation layer in `src/i18n/`. The backend,
processing hooks, API payloads, color calculations, and machine-readable exports
remain language-independent. Documentation remains in its existing language.

| Module | Responsibility |
|--------|----------------|
| `i18n/index.ts` | Initialize i18next, register supported locales and aliases, resolve preferences, synchronize document language/title/description, expose the React translation hook |
| `i18n/resources.ts` and `i18next.d.ts` | Register locale resources and type-check namespace/key references |
| `i18n/locales/<locale>/*.json` | Feature-owned strings: common, converter, parameters, filaments, preview, editor, batch, palettes, search, feedback, errors |
| `i18n/messages.ts` | Adapt canonical frontend/API error and warning strings for display without modifying their source state |
| `i18n/catalog.ts` | Resolve system preset and palette display metadata by stable identity, preserving unknown entries |
| `components/LanguageSelector.tsx` | Accessible locale control independent of converter state |

**Locale lifecycle.** `main.tsx` initializes the language before rendering React.
A supported preference in `localStorage["tinting-voxel.locale"]` takes precedence
over the browser's ordered language preferences. Chinese variants currently
resolve to Simplified Chinese (`zh-CN`); unsupported preferences fall back to
English (`en`). Storage failures do not prevent switching. All resources are
bundled for synchronous initial rendering and switching; there is no translation
service or locale-specific backend request. Future resource loading changes belong
inside this module and must preserve the mounted workspace.

**State and transport.** Components translate at render time, including errors
already on screen. Processing hooks retain canonical messages, values, and task
states; translated strings are never added to calculation dependencies. Switching
language must not re-upload files, restart processing, replace result images, or
recreate the WebGL canvas. Existing API errors have no localization contract, so
`messages.ts` contains explicit legacy string/pattern matching separate from
editable English display copy. Unknown server details remain intact. A future
structured error protocol can be supported by this adapter without coupling the
backend to UI translation keys.

**Dynamic colors and catalogs.** No fixed CMYK-to-language color dictionary is
used. Color swatches display the current entry's code/index and hex value. The
frontend code editor accepts unique letters A–Z, matching the existing backend
protocol that derives a label from `name[0].upper()`. Unedited legacy names and
all material parameters are preserved; editing a code updates only that entry's
canonical `name` to the chosen letter. Locale changes never rewrite names or
codes. Saved preset names and other user-authored text stay verbatim. System
preset/palette titles and descriptions use ID-based display lookups with supplied
text as fallback for new entries; these lookups do not define the palette's
colors or change an applied configuration. Supporting identifiers beyond the
existing single-letter protocol would require a separate data-contract migration.

**Formatting and feedback.** Complete sentences with counts use interpolation
and plural forms; visible large counts use locale-aware number formatting.
Numeric inputs, API numbers, and STL/3MF/CSV/slicer schemas retain their canonical
formats and units. Feedback context records the active UI language. Screenshot
capture renders native range/select controls in the clone to preserve their
appearance and translated labels without changing the live page.

**Adding a language or feature.** Add the same feature resource files under a new
locale directory, register them in `resources.ts`, and register its code, native
label, and matching aliases in `supportedLocales`. Add feature namespaces in
`resources.ts`; namespace subscriptions are derived from that registry. Keep
keys semantic and stable, use interpolation for variable content, and keep
user/transport data outside translation resources. Resource parity tests cover every registered locale. Current tests enforce matching keys and
interpolation parameters, locale persistence and fallback, live error updates,
dynamic color preservation, retained feedback drafts, and no redundant preview
requests. `npm test` and `npm run build` validate this boundary.

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

The production color mixing model is ONE formula for every filament
(transparent or opaque, preset or custom):

```
mu_ch(color) = ln(10) / td + k × A_ch(color)
T_ch         = exp(-mu_ch × d)

Where:
- td      = the filament's single composite transmission distance (mm),
            broadcast across channels. bambu presets hold the exact fold of
            the Phase-6 fitted scatter (ln10 × 1.48 × td_td1s^0.20 / 8.08);
            the clear preset holds staircase-measured means; user-entered
            values apply literally (base-10: t = 10^(-d/td)).
- k       = optional pigment absorption gain (default 0 = plain Beer-Lambert)
- A_ch    = per-channel absorption from the filament hex
- d       = layer height (mm)
```

Stacked colors compose through the light-loss allocation (paper Eqs. 4-8).
The Phase-6 fitted k values (K 17.65 > W 12.39 > M 8.42 > C 8.13 > Y 3.73)
survive verbatim; the retired scatter-alpha/td-remap parameters exist only
as the folded td numbers above.

Implementation: `blend_models.py` (unified formula + vectorized batch), presets: `core/color_config.py`.

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

### Built-in filament catalog

The only built-in presets are `bambu_cmyw_phase6` (four colors, default) and
`clear_cmywg` (five colors: CMYWG). `core/color_config.py` owns the canonical
registry used by preset lookup, enumeration, API responses, and cache warmup.
Removed presets have no aliases, archives, or fallback mappings. Unknown IDs
are rejected. Download, batch, and default color construction use Phase 6 CMYW.
The palette library's standard entries reference these same definitions.
Frontend initialization is checked against a shared catalog fixture, which is
also checked against the backend definitions; transparent material parameters
must not diverge between the browser and server. Custom colors remain supported.

Palette API responses and application preserve the full material configuration
(alpha, k, TD scale and gamma), matching direct preset selection. The frontend
shares one preset option list between settings and automatic parameter search.

The palette browser exposes only these same two configurations. Category
filtering and all other built-in palette definitions have been removed.
