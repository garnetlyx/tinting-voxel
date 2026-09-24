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
│   │       ├── download.py   # CSV download endpoint
│   │       ├── download_v2.py # V2 N-color endpoints (STL, SVG-STL, 3MF, print settings)
│   │       ├── filament.py   # Filament preview
│   │       ├── batch.py      # Batch processing (up to 20 images)
│   │       ├── palette.py    # Palette library
│   │       ├── param_search.py # Background parameter search + candidate previews
│   │       ├── bug_report.py  # In-app bug reports
│   │       └── health.py     # Health check endpoints
│   ├── core/             # Core algorithms
│   │   ├── blend_color.py        # Color blending (BlendTestGenerator, colors_key)
│   │   ├── blend_models.py       # Unified light-loss stacking + vectorized batch
│   │   ├── color_config.py       # Filament presets single source of truth
│   │   ├── color_materials.py    # Material properties (hex + scalar or RGB TD)
│   │   ├── code_grid.py          # Code grid generation utilities
│   │   ├── grid_sampling.py      # Code-grid RGB assembly for blend fitting
│   │   ├── plate_geometry.py     # Plate geometry calculations
│   │   └── palette_library.py    # Supported filament palettes
│   ├── services/         # Business logic
│   │   ├── image_processor.py    # Image processing + auto-downscale
│   │   ├── stl_generator.py      # STL file generation
│   │   ├── svg_stl_generator.py  # SVG-mode STL generation
│   │   ├── threemf_generator.py  # 3MF output (one object, a part per filament)
│   │   ├── threemf_writer.py     # 3MF packaging (streamed XML, shared vertices)
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
│   └── tests/            # Test suite (~700 tests)
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
├── e2e/                  # Playwright E2E tests (8 spec files, 48 tests)
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
| **3MFGenerator** | 3MF: one object with a named, colored part per filament | NumPy |
| **MeshOptimizer** | Greedy meshing to reduce box count, face culling | NumPy |
| **BlendColor (core)** | BlendTestGenerator, colors_key, CIEDE2000 matching | scikit-image, NumPy |
| **BlendModels** | Shared light-loss allocation using each material’s `T_ch = 10^(-d / TD_ch)` | NumPy |
| **ColorConfig** | Material catalog: name, hex, scalar or RGB transmission distance | dataclasses |
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
   │ whiteBackingLayers: 3                      │
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
   │ CMYW_208x208x0.56_C.stl  (Cyan layer)      │
   │ CMYW_208x208x0.56_M.stl  (Magenta layer)   │
   │ CMYW_208x208x0.56_Y.stl  (Yellow layer)    │
   │ CMYW_208x208x0.56_W.stl  (White layer)     │
   └────────────────────────────────────────────┘
```

## API Design

### Endpoints

| Endpoint | Method | Input | Output |
|----------|--------|-------|--------|
| `/api/process-image` | POST | `multipart/form-data` (image + params) | JSON (colorBlocks, processedImage) |
| `/api/download-csv` | POST | JSON (colorBlocks) | `text/csv` file |
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
| **Color Mixing Model** | Unified material transmission and light-loss allocation | `T_ch = 10^(-d / TD_ch)` | One formula and material schema for every filament |
| **Mesh Optimization** | None, Greedy meshing, Marching cubes | Greedy meshing | 70-80% reduction with simple implementation |
| **STL Format** | ASCII STL, Binary STL | Binary STL | 5x smaller files, faster parsing |
| **Separate vs Single STL** | Multi-color single file, Separate per color | Separate files | Slicer compatibility, manual filament swap support |
| **State Management** | Redux, Zustand, React hooks | Custom hook | Simpler for single-page app, no external dependencies |
| **API Communication** | REST, GraphQL, WebSocket | REST | Simple CRUD operations, stateless processing |
| **Reference Matrix Generation** | On-demand, Startup precompute | Startup precompute | Faster per-request processing, consistent results |

## Key Algorithms

### 1. Unified Color Mixing

Each material has `name`, `hex`, and one `transmission_distance` field. TD is
either a positive number or three positive numbers in RGB order. A scalar is
the equal-channel case of the same formula:

```
T_ch = 10^(-d / TD_ch)
A_ch = 1 - hex_ch / 255
```

`d` is the thickness of one color layer in mm. `Color.transmission()` owns the
transmission calculation; `blend_models.py` composes layer transmission and
hex-derived absorption with one light-loss allocation rule. The batch path and
single-code path use the same material values.

The TD mean across all materials and RGB channels determines transparency;
each material has equal weight and a scalar contributes three equal channels.
The threshold is `TRANSPARENT_TD_THRESHOLD_MM` in `core/stack_prune.py` (4.5 mm).
It controls pruning and the layer-height default, independently of preset names.
When a request omits `layerHeight`, the API resolves it from the requested
materials using the same rule; an explicit height is preserved. `GET /api/v2/filament-presets` supplies the threshold, aggregation
rule, material catalog, and print defaults to the browser.

`config/print_defaults.py` defines 0.08 mm for regular color layers and 0.84 mm
for high-transmission color layers. The latter spans three 0.28 mm slicer
layers. Exported `color_layer_height_mm` preserves color-layer thickness;
`layer_height` is the slicer layer height. Four 0.84 mm color layers plus three
backing layers form a 5.88 mm stack, corresponding to 21 slices at 0.28 mm.
Print settings record color segments as `color_layer_count` and
`backing_color_layer_count`; `object_dimensions.total_layer_count` counts actual
slicer layers, while `optical_layer_count` counts the color stack's slicer layers.
The example therefore reports 4 color segments, 3 backing segments, 21 total
slicer layers, and 12 color-stack slicer layers.

Three backing color layers are printed by default, in one of the set's filaments:
the one the user picks, or else the filament closest to white by CIEDE2000. Its
actual layers are appended to the predicted stack under the same white
illumination; no external backing color is added.

Parameter search scores the current configuration and the candidates of a
pattern search by the mean CIEDE2000 between the image on the model grid and
each simulated print. The job returns previews in evaluation order with
`candidate_id`, `is_baseline` and `score`; the dialog ranks them as they arrive,
and choosing one applies it and cancels the rest.

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
- **Size Limits**: 10MB max upload; the model grid holds at most 2M cells and 4096px per side (larger images are resampled)
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

`core/color_config.py` owns the four built-in presets:
`bambu_cmywk` (five colors, default), `bambu_cmyw` (four colors),
`clear_cmyg`, and `clear_cmyw`. All four presets use RGB-channel TD values. Bambu CMYW is derived from
CMYWK without the K material. Their effective TDs come from the existing Bambu
staircase observations; photo-specific calibration terms are not product parameters.

Preset lookup, palette responses, and browser initialization consume this
registry. The browser fetches catalog values from the API and exposes retry
when the catalog cannot load. It has no duplicate built-in material table.
Unknown preset IDs are rejected.

Custom materials use the same schema. The editor shows one TD control and an
optional expansion for RGB values. Equal RGB values have the same predictions
and cache identity as a scalar. Palette selection and saved custom presets
preserve the complete transmission-distance value.
