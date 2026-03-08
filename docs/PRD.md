# Product Requirements Document (PRD)

**Product Name**: img2stl
**Version**: 1.0
**Last Updated**: 2026-03-08
**Status**: In Development

---

## 1. Overview

### 1.1 Product Vision
Transform any image into physically accurate, multi-color 3D-printable STL files using CMYK color separation and optical color mixing principles. Enable makers, artists, and engineers to create vibrant, full-color 3D prints using transparent filaments.

### 1.2 Problem Statement
Current 3D printing solutions for color images face limitations:
- Multi-material printers are expensive and require complex calibration
- Color accuracy is poor with simple layer stacking
- File sizes are bloated with inefficient mesh generation
- No tools exist that map colors using optical physics (Beer-Lambert law)

img2stl solves these problems by:
- Using scientifically-grounded color mixing models based on light transmission
- Generating optimized STL files with greedy meshing (reducing file size by up to 80%)
- Providing real-time parameter adjustment and preview
- Supporting standard CMYK primary colors for predictable results

### 1.3 Goals & Success Metrics
| Goal | Metric | Target |
|------|--------|--------|
| Accurate color reproduction | Delta-E color difference | < 10 (perceptually acceptable) |
| File size optimization | STL file size reduction | > 70% vs naive boxing |
| Processing performance | Image processing time | < 5s for 512x512px |
| User adoption | Active users | 100 users/month (6 months) |
| Export success rate | Successful STL downloads | > 95% |

---

## 2. Users & Personas

### 2.1 Target Users
- Hobbyist 3D printing enthusiasts
- Product designers prototyping with color
- Artists exploring new mediums
- Educators teaching optics and additive manufacturing
- Professional makers requiring color prototypes

### 2.2 User Personas

#### Persona 1: Alex - Hobbyist Maker
- **Background**: 3D printing enthusiast with Bambu Lab P1S, comfortable with technical tools
- **Goals**: Create colorful decorative prints and gifts without buying a multi-material system
- **Pain Points**: Existing tools produce bland single-color prints or require expensive upgrades
- **Usage Context**: Weekend projects, experimenting with transparent PETG filaments

#### Persona 2: Jordan - Product Designer
- **Background**: Industrial designer prototyping consumer products
- **Goals**: Quickly validate color schemes and visual appearance before manufacturing
- **Pain Points**: Traditional CAD tools don't support image-based color mapping, prototype services are slow
- **Usage Context**: Design validation during working hours, needs fast iteration

#### Persona 3: Sam - STEM Educator
- **Background**: High school physics/engineering teacher with classroom 3D printer
- **Goals**: Demonstrate optical color mixing and additive manufacturing principles
- **Pain Points**: Lack of educational tools that connect theory (Beer-Lambert law) to practice
- **Usage Context**: Classroom demonstrations, student projects

---

## 3. Use Cases & Scenarios

### 3.1 Core Use Cases
| ID | Use Case | Priority | User |
|----|----------|----------|------|
| UC-01 | Convert photo to layered CMYK STL files | P1 | All |
| UC-02 | Adjust color extraction parameters | P1 | Alex, Jordan |
| UC-03 | Preview processed image before export | P1 | All |
| UC-04 | Download optimized STL files as ZIP | P1 | All |
| UC-05 | Export color data as CSV for analysis | P2 | Jordan, Sam |
| UC-06 | Customize layer height and pixel size | P1 | Jordan |
| UC-07 | Process images up to 512x512px | P1 | All |

### 3.2 User Flows

#### Flow 1: Basic Image-to-STL Conversion
1. User uploads image file (PNG, JPG, etc.)
2. System processes image with default parameters (maxColors=10, threshold=50)
3. System displays extracted color blocks and processed preview
4. User reviews color accuracy in side-by-side comparison
5. User downloads ZIP containing 4 STL files (C, M, Y, W layers)
6. User prints files sequentially with corresponding filament colors

#### Flow 2: Parameter Tuning for Quality
1. User uploads complex image with many colors
2. System processes with default parameters
3. User observes color blocks don't match original well
4. User increases maxColors to 15, adjusts colorThreshold to 30
5. User clicks "Reprocess" to regenerate with new parameters
6. System updates preview and color blocks
7. User iterates until satisfied, then downloads

#### Flow 3: Educational Demonstration
1. Teacher uploads simple gradient image
2. System extracts CMYK layers
3. Teacher downloads CSV to show color mapping data
4. Class examines how RGB colors map to CMYK combinations
5. Students print layers and observe optical color mixing
6. Teacher uses physical prints to explain Beer-Lambert law

---

## 4. Feature Scope

### 4.1 In Scope (Must Have - MVP)
- [x] **Image Upload**: Support PNG, JPG, JPEG formats up to 10MB
- [x] **Color Extraction**: K-means clustering for dominant color detection
- [x] **CMYK Mapping**: Map extracted colors to CMYK primaries using LAB color space
- [x] **Beer-Lambert Model**: Calculate layered color mixing using optical physics
- [x] **STL Generation**: Generate separate STL files for C, M, Y, W layers
- [x] **Greedy Meshing**: Optimize mesh by merging adjacent pixels (reduce file size 70%+)
- [x] **Parameter Controls**:
  - maxColors (1-20): number of dominant colors to extract
  - colorThreshold (0-100): sensitivity for color merging
  - layerHeight (0.01-1.0mm): thickness of each layer
  - pixelSize (0.01-1.0mm): XY dimension of each pixel
- [x] **Real-time Preview**: Side-by-side comparison of original vs processed image
- [x] **CSV Export**: Export color block data for analysis
- [x] **ZIP Download**: Package all STL files into single archive

### 4.2 In Scope (Nice to Have - Post-MVP)
- [ ] **Custom Color Profiles**: Allow users to define custom CMYK primaries (hex values)
- [ ] **Transmission Distance Tuning**: Adjust Beer-Lambert parameters per color
- [ ] **Batch Processing**: Process multiple images in one session
- [ ] **3D Preview**: WebGL preview of layered STL files
- [ ] **Image Pre-processing**: Auto-crop, resize, filters
- [ ] **Color Palette Library**: Save/load favorite color configurations
- [ ] **Print Settings Export**: Generate slicer config files (e.g., for Bambu Studio)
- [ ] **Advanced Metrics**: Display color accuracy metrics (Delta-E)

### 4.3 Out of Scope
- **Vector Image Support**: SVG/PDF inputs (raster images only)
- **Non-CMYK Color Systems**: RGB-only or spot color workflows
- **Direct Slicer Integration**: Plugin for PrusaSlicer/Cura (requires separate project)
- **Physical Material Calibration**: Per-filament tuning (assumes standard transparent PETG)
- **Texture Mapping**: Complex surface patterns beyond flat color blocks
- **Multi-page STL**: Single-file multi-color STL (incompatible with most slicers)

---

## 5. UI/UX Requirements

### 5.1 Design Principles
- **Simplicity First**: Core workflow should be achievable in 3 clicks (upload, adjust, download)
- **Immediate Feedback**: Show processing status and preview updates in real-time
- **Progressive Disclosure**: Advanced parameters hidden by default, accessible via settings toggle
- **Visual Clarity**: Side-by-side image comparison for easy quality assessment
- **Forgiving**: Allow users to adjust and reprocess without re-uploading image

### 5.2 Key Screens/Views
| Screen | Purpose | Key Elements |
|--------|---------|--------------|
| Main Converter | Primary workspace | Image uploader, parameter panel, preview comparison, download buttons |
| Parameter Panel | Adjust extraction settings | Sliders for maxColors, colorThreshold, layerHeight, pixelSize |
| Image Comparison | Visual validation | Original image (left), processed preview (right) |
| Color Blocks List | Show extracted colors | Color swatches, RGB values, pixel counts, hex codes |
| Download Section | Export results | CSV button, STL ZIP button, loading states |

### 5.3 Interaction Patterns
- **Drag-and-Drop Upload**: Primary image upload method (click fallback)
- **Live Parameter Updates**: Sliders update values in real-time with debouncing
- **Manual Reprocess**: Explicit "Reprocess" button to avoid excessive API calls
- **Loading States**: Spinner overlay during processing with progress indication
- **Error Handling**: Friendly error messages for upload failures, processing errors
- **Responsive Layout**: Single-column mobile, two-column desktop

---

## 6. Technical Requirements

### 6.1 Platform & Compatibility
- **Frontend**: Modern browsers with ES6+ support (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)
- **Backend**: Python 3.8+ runtime
- **Deployment**: Docker containerizable, cloud-ready (AWS, Vercel, Railway)
- **File Support**: PNG, JPG, JPEG (max 10MB per image)
- **Image Size**: Up to 1024x1024px (512x512px recommended for performance)

### 6.2 Performance Requirements
| Metric | Requirement |
|--------|-------------|
| Image Processing Time | < 5s for 512x512px, < 15s for 1024x1024px |
| STL Generation Time | < 10s for 256x256px mesh with greedy optimization |
| API Response Time | < 500ms (excluding processing) |
| Frontend Load Time | < 2s on 3G connection |
| Memory Usage (Backend) | < 512MB RAM per concurrent request |
| File Size | < 5MB per STL file after optimization |

### 6.3 Security Requirements
- **File Validation**: Verify uploaded files are valid images (magic number check)
- **Size Limits**: Reject files > 10MB to prevent DoS
- **Input Sanitization**: Validate all parameter inputs (range checks)
- **CORS Configuration**: Restrict origins to trusted domains
- **No Persistent Storage**: Delete temporary files after processing
- **Rate Limiting**: Max 10 requests/minute per IP (future)

### 6.4 Data Requirements
- **No User Data Storage**: Stateless processing, no database required
- **Temporary File Handling**: Images stored in memory during processing, cleaned up immediately
- **Export Format**:
  - STL: Binary STL format (smaller than ASCII)
  - CSV: UTF-8 encoding, standard column headers
  - ZIP: Standard ZIP compression, maximum compatibility

---

## 7. Constraints & Assumptions

### 7.1 Constraints
- **Technical**:
  - Python backend limits concurrent processing (CPU-bound)
  - Browser memory limits large image uploads
  - STL file format doesn't support embedded color data (requires separate files)
- **Business**:
  - No budget for cloud infrastructure (local/self-hosted deployment)
  - Single developer team (limited maintenance bandwidth)
- **Resource**:
  - Open-source dependencies only (no licensed libraries)
  - No user authentication/accounts (MVP)

### 7.2 Assumptions
- **User has 3D printer** capable of filament swapping (manual or AMS)
- **User has transparent CMYK filaments** (standard Bambu Lab or similar)
- **Users understand basic 3D printing** (know how to import/slice STL files)
- **Beer-Lambert model is accurate** for common transparent PETG filaments
- **Greedy meshing** doesn't compromise print quality (minimal artifacts)
- **LAB color space** provides perceptually accurate color matching

### 7.3 Dependencies
- **External Libraries**:
  - FastAPI (backend framework)
  - numpy-stl (STL mesh generation)
  - scikit-learn (K-means clustering)
  - Pillow (image processing)
  - React 19 (frontend framework)
  - Vite (build tool)
- **Infrastructure**:
  - Node.js 18+ (frontend build)
  - Python 3.8+ (backend runtime)
  - Modern browser with File API support

---

## 8. Release Planning

### 8.1 MVP Scope (v1.0 - Current)
**Goal**: Functional image-to-STL converter with core features

**Features**:
- [x] Image upload (PNG, JPG)
- [x] K-means color extraction
- [x] CMYK color mapping (Beer-Lambert model)
- [x] Layered STL generation with greedy meshing
- [x] Parameter adjustment UI (maxColors, colorThreshold, layerHeight, pixelSize)
- [x] Real-time preview
- [x] CSV export
- [x] ZIP download
- [x] Comprehensive test suite (unit + integration)
- [x] Documentation (README, SETUP, CLAUDE)

**Status**: Feature-complete, in testing

### 8.2 Future Phases

| Phase | Features | Priority | Target |
|-------|----------|----------|--------|
| **Phase 1.1** (Post-MVP Polish) | - Custom CMYK color profiles<br>- Advanced error handling<br>- Processing progress bar<br>- Image pre-processing (crop, resize) | P2 | Q2 2026 |
| **Phase 2** (Enhancement) | - 3D preview (WebGL)<br>- Batch processing<br>- Color palette library<br>- Print settings export | P2 | Q3 2026 |
| **Phase 3** (Scale) | - User accounts<br>- Cloud deployment<br>- API rate limiting<br>- Usage analytics<br>- Docker containerization | P3 | Q4 2026 |
| **Phase 4** (Ecosystem) | - Slicer plugins (Bambu Studio, PrusaSlicer)<br>- Material calibration wizard<br>- Community color profiles<br>- Mobile app | P3 | 2027+ |

---

## 9. Current Implementation Status

### 9.1 Backend (Python/FastAPI)
**Status**: ✅ Implemented

**Completed**:
- FastAPI application with modular routes (`/api/process-image`, `/api/download-csv`, `/api/download-stl`)
- Pydantic models for request/response validation
- Image processing service (K-means clustering, color extraction)
- STL generation service with Beer-Lambert color mixing
- CSV generation service
- Mesh optimization service (greedy meshing)
- Vector processing utilities
- Configuration management (environment-based settings)
- Health check endpoint
- CORS middleware for cross-origin requests
- Comprehensive test suite (pytest, 90%+ coverage)

**Key Files**:
- `backend/main.py`: FastAPI app initialization, lifespan management
- `backend/core/blend_color.py`: Beer-Lambert color model, CMYK mapping (678 lines)
- `backend/services/stl_generator.py`: STL mesh generation, color mapping
- `backend/services/mesh_optimizer.py`: Greedy meshing algorithm
- `backend/api/models.py`: Request/response schemas
- `backend/tests/`: Unit and integration tests

### 9.2 Frontend (React/TypeScript)
**Status**: ✅ Implemented

**Completed**:
- React 19 with TypeScript (strict mode)
- Vite build system with HMR
- Custom hook for image processing logic (`useImageProcessor`)
- Modular component architecture
- Parameter panel with live controls
- Image uploader with drag-and-drop
- Side-by-side image comparison
- Color blocks visualization
- Download buttons (CSV, STL)
- Loading states and error handling
- Tailwind CSS styling
- API proxy configuration

**Key Files**:
- `src/pages/Converter.tsx`: Main page component
- `src/hooks/useImageProcessor.ts`: Processing logic and state management
- `src/components/`: UI components (ImageUploader, ParameterPanel, etc.)
- `src/api/client.ts`: API integration layer

### 9.3 Infrastructure
**Status**: 🟡 Partial

**Completed**:
- [x] Git repository with conventional commits
- [x] README and setup documentation
- [x] Development scripts (npm run dev, backend scripts)
- [x] Python virtual environment setup
- [x] Requirements.txt with pinned versions
- [x] Basic .gitignore configuration
- [x] Test suite with pytest

**Pending**:
- [ ] Docker containerization (Dockerfile, docker-compose)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Cloud deployment configuration
- [ ] Production environment variables
- [ ] Logging and monitoring setup
- [ ] Performance benchmarking suite

---

## 10. API Reference

### 10.1 POST /api/process-image
**Purpose**: Process uploaded image and extract color blocks

**Request**:
- Content-Type: `multipart/form-data`
- Parameters:
  - `image`: File (required) - Image file
  - `maxColors`: int (default: 10) - Max colors to extract
  - `colorThreshold`: float (default: 50) - Color merge threshold
  - `pixelSize`: float (default: 0.08) - Pixel size in mm

**Response** (200 OK):
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

### 10.2 POST /api/download-csv
**Purpose**: Download color data as CSV

**Request**:
```json
{
  "colorBlocks": [...]
}
```

**Response** (200 OK):
- Content-Type: `text/csv`
- Filename: `color_blocks.csv`

### 10.3 POST /api/download-stl
**Purpose**: Generate and download layered STL files

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

**Response** (200 OK):
- Content-Type: `application/zip`
- Filename: `CMYW_{width}x{height}x{total_height}.zip`
- Contents: `CMYW_..._C.stl`, `CMYW_..._M.stl`, `CMYW_..._Y.stl`, `CMYW_..._W.stl`

### 10.4 GET /api/health
**Purpose**: Health check endpoint

**Response** (200 OK):
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## Appendix

### A. Glossary
| Term | Definition |
|------|------------|
| **Beer-Lambert Law** | Optical physics law describing light absorption/transmission through layers |
| **CMYK** | Cyan, Magenta, Yellow, Key (black) - subtractive color model |
| **Greedy Meshing** | Optimization algorithm that merges adjacent identical pixels into larger boxes |
| **K-means Clustering** | Machine learning algorithm for grouping similar colors |
| **LAB Color Space** | Perceptually uniform color space (L=lightness, a/b=color axes) |
| **STL** | Standard Tessellation Language - 3D mesh file format |
| **AMS** | Automatic Material System (Bambu Lab filament changer) |
| **Delta-E** | Perceptual color difference metric (< 1 = imperceptible, < 10 = acceptable) |

### B. References
- [Beer-Lambert Law](https://en.wikipedia.org/wiki/Beer%E2%80%93Lambert_law) - Optical transmission physics
- [CIELAB Color Space](https://en.wikipedia.org/wiki/CIELAB_color_space) - Perceptual color matching
- [Greedy Meshing](https://0fps.net/2012/06/30/meshing-in-a-minecraft-game/) - Mesh optimization technique
- [STL Format Specification](https://en.wikipedia.org/wiki/STL_(file_format)) - 3D mesh file format

### C. Change Log
| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-01-27 | 1.0 | Initial PRD created from existing codebase | Claude |
| 2026-01-21 | 0.9 | MVP features implemented, greedy meshing added | [TBD] |
| [TBD] | 0.1 | Project initiated | [TBD] |

---

## Notes

### Technical Highlights
1. **Beer-Lambert Model**: Unlike simple layer stacking, img2stl uses optical physics to predict how light transmits through transparent layers, producing accurate color mixing
2. **Greedy Meshing**: Reduces STL file sizes by 70-80% by merging adjacent pixels into larger boxes, critical for large images
3. **LAB Color Space**: Ensures perceptually accurate color matching (humans perceive colors logarithmically, not linearly)
4. **Stateless Architecture**: No database required, all processing in-memory for simplicity and scalability

### Design Decisions
- **Separate STL Files**: Most slicers don't support multi-color single files; separate files allow manual filament swaps
- **Default 4 Layers**: Balances color depth with print time; more layers = better color but longer prints
- **CMYK (not RGB)**: Transparent filaments use subtractive color mixing (like printing), not additive (like screens)
- **No Authentication**: MVP prioritizes functionality over user management; can add later if needed

### Future Considerations
- **GPU Acceleration**: For image processing and K-means clustering (scikit-learn supports cuML)
- **WebAssembly**: Port Beer-Lambert calculations to WASM for client-side processing
- **Progressive Web App**: Enable offline usage with cached resources
- **Material Database**: Community-contributed filament transmission profiles for better accuracy
