# Product Requirements Document (PRD)

**Product Name**: tinting-voxel
**Version**: 2.0
**Last Updated**: 2026-09-09
**Status**: In Development — feature-complete beyond original MVP

---

## 1. Overview

### 1.1 Product Vision

Transform any image into physically accurate, multi-color 3D-printable files
using **N-color** filament separation and optical color mixing principles
(Beer-Lambert law). Enable makers, artists, and engineers to create vibrant,
full-color 3D prints using standard transparent filaments on any multi-material
FDM printer (Bambu Lab AMS, Prusa MMU, tool-changers, manual filament swaps).

### 1.2 Problem Statement

Current 3D-printing color solutions face a combination of limitations:

- Multi-material printers are expensive and require complex calibration.
- Color accuracy is poor with simple layer stacking.
- File sizes are bloated with inefficient mesh generation.
- Most tools cannot generalize: swapping a filament means reprinting a full
  calibration board (e.g. existing tools' 5⁴=625-cell LUT per filament set).
- No tool combines an optical-physics color model with a full web UI, REST
  API, and arbitrary-filament configurability.

tinting-voxel solves these by:

- Using a scientifically-grounded color mixing model based on light
  transmission (`T_ch = 10^(-d / TD_ch)`, light-loss allocation stacking).
- Generating optimized meshes with greedy meshing (70–80% box-count
  reduction).
- Supporting **any N-color filament configuration (4–16 colors)** with
  user-defined hex values and scalar or RGB transmission distance.

### 1.3 Goals & Success Metrics

| Goal | Metric | Target |
|------|--------|--------|
| Accurate color reproduction | CIELAB Delta-E vs printed plate | Target: < 10 |
| File size optimization | STL box-count reduction | 70–80% vs naive per-pixel boxing |
| Processing performance | Image processing time | < 5s for 512×512px |
| User adoption | Active users | 100 users/month (6 months) |
| Export success rate | Successful downloads | > 95% |
| Test health | Backend test pass rate | > 95% across ~700 tests |

---

## 2. Users & Personas

### 2.1 Target Users

- Hobbyist 3D-printing enthusiasts (Bambu Lab P1S / X1C with AMS).
- Product designers prototyping with color.
- Artists exploring new physical mediums.
- Educators teaching optics and additive manufacturing.
- Etsy / online sellers producing custom lithophane-style gifts in batches.
- Researchers exploring transparent-filament color models.

### 2.2 User Personas

#### Persona 1 — Alex, Hobbyist Maker
- Bambu Lab P1S, comfortable with technical tools.
- Wants colorful decorative prints without buying a multi-material upgrade.
- Uses the curated palette library and the 3D preview to iterate before
  printing.

#### Persona 2 — Jordan, Product Designer
- Industrial designer prototyping consumer products.
- Needs fast iteration and configurable N-color filaments to match brand
  palettes; uses batch processing for variant studies.

#### Persona 3 — Sam, STEM Educator
- Classroom 3D printer, demonstrates optical color mixing.
- Uses CSV export and the Beer-Lambert model walkthroughs as teaching
  material.

#### Persona 4 — Mira, Etsy Seller
- Produces 10–20 custom prints per week.
- Uses batch processing (up to 20 images) and print-settings export to feed
  directly into Bambu Studio.

---

## 3. Use Cases & Scenarios

### 3.1 Core Use Cases

| ID | Use Case | Priority |
|----|----------|----------|
| UC-01 | Convert photo to layered N-color STL/3MF files | P1 |
| UC-02 | Configure 4–16 filament primaries (hex + transmission) | P1 |
| UC-03 | Preview processed image + 3D WebGL render before export | P1 |
| UC-04 | Download optimized output (STL ZIP, 3MF, SVG-STL, CSV) | P1 |
| UC-05 | Export slicer print-settings JSON | P1 |
| UC-06 | Process a batch of up to 20 images | P2 |
| UC-07 | Auto-search best processing parameters for an image | P2 |
| UC-08 | Use curated color palette as a starting point | P2 |

### 3.2 User Flows

#### Flow 1 — Basic Image-to-Mesh Conversion
1. User uploads PNG/JPG (≤10MB); large images are resampled to the model grid (≤2M cells, ≤4096px per side) at their physical size.
2. Backend extracts dominant colors via K-means in CIELAB space.
3. Backend maps colors to the configured N-color set using shared transmission
   and light-loss allocation with CIEDE2000 distance.
4. Frontend shows side-by-side original vs. simulated print + 3D WebGL
   preview.
5. User downloads STL ZIP / 3MF / CSV / print settings.

#### Flow 2 — N-Color Filament Configuration
1. User picks Bambu CMYWK (default), Bambu CMYW, Clear CMYG, or Clear CMYW.
2. User edits generic color codes (unique A–Z letters), hex values, and one TD value. TD optionally expands into three RGB channel values. Codes identify arbitrary colors; they do not constrain the palette to CMYK.
3. Filament preview matrix regenerates showing achievable color gamut.
4. Configuration persists across sessions via localStorage.

#### Flow 3 — Batch Processing
1. User drops up to 20 images.
2. Each image is processed with shared settings.
3. User downloads a single STL ZIP per image or a combined batch download.

#### Flow 4 — Parameter Search (auto-tune)
1. User uploads an image and opens the parameter-search modal.
2. Backend scores the current settings, then pattern-searches the mode's settings
   (pixel: `maxColors` / `colorThreshold`; SVG: color count, simplification,
   minimum area) by the mean CIEDE2000 between the image and each simulated print.
3. Previews rank closest first as they finish; the user picks one at any time,
   which applies it and stops the search, and proceeds to export.

> Material measurements belong to the published research analysis. Production
> material inputs are limited to hex color and scalar or RGB transmission distance.

---

## 4. Feature Scope

### 4.1 Shipped (current state)

**Image input**
- PNG / JPG / JPEG / BMP / GIF / WebP upload with magic-byte validation
- Resample to the model grid: at most `max_model_cells` cells and `MAX_PROCESSING_DIMENSION` (4096px) per side
- Canvas crop/resize editor (frontend)
- Drag-and-drop + click upload

**Color processing**
- K-means clustering (vectorized, CIELAB distance) for color extraction
- N-color mapping via one transmission formula, `T_ch = 10^(-d / TD_ch)`
- CIEDE2000 perceptual matching with hue-preservation for dark chromatic colors
- Colors matched as seen against the image's white: off-whites print white in
  images with deep shadows; faded, high-key and Morandi palettes keep their colors
- Every layer order is a candidate, so white layers over a color print its pale tints
- Four built-in filament presets: Bambu CMYWK (default), Bambu CMYW, Clear CMYG, and Clear CMYW.
  Custom configurations remain supported; removed preset IDs are rejected.
- Palette browser for the four supported filament configurations
- Filament preview matrix with pagination for large N

**Output formats**
- Color-block CSV
- V2: N-color STL ZIP, N-color SVG-STL, **3MF** (one object with a named,
  colored part per filament), **SVG-3MF**, print-settings JSON
- Greedy meshing (70–80% box-count reduction), face culling
- Double-sided print support

**UX**
- Side-by-side original/processed comparison
- 3D WebGL preview (three.js InstancedMesh, orbit controls, material caching)
- Parameter panel (maxColors, colorThreshold, layerHeight, pixelSize, detail
  presets with nozzle-line-width defaults)
- Batch processor UI (up to 20 images)
- Filament config panel + preset manager; one TD field with optional RGB expansion
- Regular color layers default to 0.08 mm; high-transmission color layers to 0.84 mm (three 0.28 mm slicer layers)
- Three backing color layers by default, printed in a filament picked from the current set (default: the filament closest to white)
- Palette library selector
- Parameter-search modal with backend warmup UX
- Color adjustment panel
- In-app bug reports (optional screenshot, settings, diagnostics; email delivery via Resend)
- English and Simplified Chinese UI with live locale switching

**Infrastructure / API**
- FastAPI app with V1 + V2 routes, param-search, batch, palette, filament,
  health, analytics, bug-report
- `slowapi` rate limiting on all endpoints
- `@handle_api_errors` standardized error handling
- File upload validators (extension, size, magic bytes)
- In-memory usage analytics
- Docker multi-stage build + Railway / Fly.io / docker-compose configs

**Quality**
- ~700 backend tests, 171 frontend Vitest tests (22 files), 48 Playwright E2E tests (8 spec files)
- QA regression suite (R1–R16+) documenting 190+ bugs fixed

### 4.2 In Progress / Planned

- **Max-dimension preset chips** in the frontend (180 / 250 / 300mm).
- **Production hardening** — thread locks on global matrices, bounded
  analytics, non-root Docker user (see TODO P0/P1).

The backend material catalog is the single source for preset values and print
defaults. Bambu and clear presets use RGB-channel TD; custom materials accept a single TD or three channels.

### 4.3 Out of Scope

- Direct in-slicer plugin (Bambu Studio / PrusaSlicer / Cura) — handled via
  exported 3MF + print-settings JSON instead.
- Cloud user accounts / saved profiles (deferred to a later phase).
- GPU acceleration (cuML) — not critical at current scale.
- Palette-specific empirical codebooks as the primary runtime path.

---

## 5. UI/UX Requirements

### 5.1 Design Principles

- **Simplicity first**: core flow is upload → tune → download.
- **Immediate feedback**: live preview, debounced parameter updates,
  background warmup for long jobs.
- **Progressive disclosure**: advanced parameters and filament config hidden
  by default.
- **Forgiving**: re-process without re-uploading; persistent filament config.

### 5.2 Key Screens

| Screen | Purpose |
|--------|---------|
| Converter | Main workspace: upload, parameter panel, preview, downloads |
| Parameter Panel | maxColors, colorThreshold, layerHeight, pixelSize, detail presets |
| Filament Config Panel | N-color preset + code / hex / one TD field with optional RGB expansion |
| Language Selector | English / Simplified Chinese workspace preference |
| Filament Preview | Achievable color gamut matrix |
| Image Comparison | Original vs simulated print |
| 3D Preview | three.js WebGL render with orbit controls |
| Batch Processor | Multi-image queue + shared settings |
| Palette Library | Curated palette picker |
| Image Editor | Canvas crop / resize |
| Parameter Search Modal | Auto-tune sweep with progress |

### 5.3 Interaction Patterns

- The workspace supports English and Simplified Chinese, with browser-language
  detection on first visit and a persistent manual choice.
- Switching language preserves the current image, parameters, processing results,
  custom colors, and feedback draft; it does not initiate another conversion.
- Interface text, tooltips, accessibility labels, known errors, and system catalog
  metadata are localized. User text, arbitrary color codes, and machine-readable
  exports preserve their original values. Backend and documentation translation
  are outside the localization scope.

- Drag-and-drop upload (with click fallback).
- Debounced live parameter updates + explicit "Reprocess".
- Loading spinners / progress for long jobs (param-search, batch).
- Friendly, granular error messages.
- Single-column mobile, multi-column desktop.

---

## 6. Technical Requirements

### 6.1 Platform & Compatibility

- **Frontend**: Modern browsers with ES6+ + WebGL (Chrome 90+, Firefox 88+,
  Safari 14+, Edge 90+).
- **Backend**: Python 3.8+ runtime (type hints throughout).
- **Deployment**: Docker, Railway, Fly.io, or self-hosted.
- **File support**: PNG, JPG, JPEG, BMP, GIF, WebP (≤10MB; resampled to at
  most 2M cells and 4096px per side, keeping the physical size).

### 6.2 Performance Requirements

| Metric | Requirement |
|--------|-------------|
| Image processing | < 5s for 512×512, < 15s for 1024×1024 |
| STL generation | < 10s for 256×256 mesh with greedy optimization |
| API response (excl. processing) | < 500ms |
| Frontend load | < 2s on 3G |
| Memory per request | < 512MB |
| Per STL file size | < 5MB after optimization |

### 6.3 Security Requirements

- File validation: magic-byte check, extension allow-list, size cap.
- Input sanitization: Pydantic validators with bounds on all parameters.
- CORS restricted to configured origins; methods limited to
  GET/POST/OPTIONS.
- CSV injection prevention (`csv.QUOTE_ALL`).
- Path-traversal protection on SPA static serving.
- Rate limiting (`slowapi`, 10/min default).
- No persistent storage of user data.

### 6.4 Data Requirements

- Stateless processing — no database.
- Temporary images held in-memory and cleaned up immediately.
- In-memory analytics (to be bounded — see TODO P0).

---

## 7. Constraints & Assumptions

### 7.1 Constraints

- Python backend limits concurrent CPU-bound processing.
- Browser memory limits very large image uploads.
- STL format does not embed color — separate per-color files or 3MF objects
  required.
- Single-developer bandwidth.

### 7.2 Assumptions

- User has a multi-material FDM printer (AMS / MMU / tool-changer / manual
  swap).
- User has transparent CMYK (and optionally additional) filaments.
- User understands basic slicing workflow.
- Material predictions use the configured hex color, TD, and physical color-layer thickness.

### 7.3 Dependencies

- **Backend**: FastAPI, numpy-stl, Pillow, scikit-learn, scikit-image,
  trimesh, lxml, slowapi, pydantic.
- **Frontend**: React 19, TypeScript (strict), Vite, Tailwind CSS, three.js,
  lucide-react.
- **Testing**: pytest, Vitest, Playwright.

---

## 8. Release Planning

### 8.1 v1.0 — Original MVP (shipped 2026-01)
CMYK-only conversion, greedy meshing, STL/CSV export, parameter UI,
real-time preview, comprehensive test suite.

### 8.2 v1.x — Post-MVP polish (shipped)
Custom color profiles, advanced error handling, image editor, 3MF output,
base plate, color adjustment, progress bars.

### 8.3 v2.0 — N-color engine (current)
Dynamic 4–16 color support, V2 API (STL / SVG-STL / 3MF / SVG-3MF / print
settings), batch processing, palette library, 3D WebGL preview, double-sided,
param search, Docker/cloud deploy. Calibration performed offline.

### 8.4 Future phases

| Phase | Features | Target |
|-------|----------|--------|
| 2.1 Accuracy | Verify material TD values and their measurement provenance | Q3 2026 |
| 2.2 Hardening | Thread locks, bounded analytics, non-root Docker, SVG complexity caps | Q3 2026 |
| 3 Ecosystem | Slicer-preset partnerships, filament manufacturer profiles, community palette submissions | Q4 2026 |
| 4 Scale | User accounts, cloud-saved profiles, monitoring (Prometheus), error tracking (Sentry) | 2027+ |

---

## 9. API Reference (summary)

### Image Processing and CSV
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/process-image` | Process image (pixel/SVG modes) |
| POST | `/api/simulate-preview` | Simulated print preview (vector mode) |
| POST | `/api/download-csv` | Color data CSV |

### V2 (N-color)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/download-stl` | N-color STL ZIP |
| POST | `/api/v2/download-svg-stl` | N-color SVG-mode STL |
| POST | `/api/v2/download-3mf` | 3MF with named color objects |
| POST | `/api/v2/download-svg-3mf` | SVG-mode 3MF |
| POST | `/api/v2/print-settings` | Slicer print-settings JSON |
| GET  | `/api/v2/filament-presets` | Available presets |

### Other
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/filament-preview` | Color gamut matrix |
| POST | `/api/batch/process` | Batch (≤20 images) |
| POST | `/api/batch/download-stl` | Batch STL download |
| POST | `/api/bug-report` | Submit in-app bug report (optional screenshot) |
| POST | `/api/param-search` | Start one parameter sweep job |
| GET  | `/api/param-search/progress/{job_id}` | Poll new previews and job status |
| DELETE | `/api/param-search/progress/{job_id}` | Cancel a sweep job |
| GET  | `/api/palettes/` | List palettes |
| GET  | `/api/palettes/{id}` | Get palette |
| GET  | `/api/analytics` | Usage analytics |
| GET  | `/api/cache-stats` | Reference-matrix cache stats |
| GET  | `/api/health` | Health check |
| GET  | `/api/health/detailed` | Detailed health check (per-subsystem status) |

Full OpenAPI spec at `/docs` when the backend is running.

---

## Appendix

### A. Glossary

| Term | Definition |
|------|------------|
| **Beer-Lambert Law** | Layer transmission expressed with transmission distance: `T_ch = 10^(-d / TD_ch)` |
| **Transmission Distance (TD)** | Material distance in mm at which channel transmission is 10%; one value or three values in RGB order |
| **CMYK / CMYWK** | Subtractive color models (Cyan, Magenta, Yellow, White/[Key]) |
| **Greedy Meshing** | Algorithm merging adjacent identical pixels into larger rectangles |
| **K-means** | Clustering algorithm for grouping similar colors |
| **CIELAB / CIEDE2000** | Perceptually uniform color space / perceptual difference metric |
| **3MF** | 3D Manufacturing Format — modern mesh format supporting color/material metadata |
| **AMS / MMU** | Automatic Material System (Bambu) / Multi-Material Unit (Prusa) |

### B. References

- [Beer-Lambert Law](https://en.wikipedia.org/wiki/Beer%E2%80%93Lambert_law)
- [CIELAB Color Space](https://en.wikipedia.org/wiki/CIELAB_color_space)
- [CIEDE2000](https://en.wikipedia.org/wiki/Color_difference#CIEDE2000)
- [Greedy Meshing](https://0fps.net/2012/06/30/meshing-in-a-minecraft-game/)
- [3MF Specification](https://3mf.io/specification/)
- [Kubelka-Munk theory](https://en.wikipedia.org/wiki/Kubelka%E2%80%93Munk_theory)

### C. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-08-14 | 2.1 | Calibration CLI/research data split out of this repo; docs aligned to post-split state |
| 2026-06-19 | 2.0 | PRD rewritten to reflect N-color V2 API, batch, 3MF, palette library, 3D preview, calibration system (Phase 6/7), 878 backend tests |
| 2026-03-08 | 1.1 | Calibration section, presets, CLI workflow |
| 2026-01-27 | 1.0 | Initial PRD from existing codebase |
