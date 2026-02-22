# Color Blending Functions

Mathematical reference for all color blending algorithms in img2stl. Each function computes the perceived RGB color of stacked translucent filament layers on a white backing.

**Implementation**: `backend/core/blend_color.py`
**Calibration data**: see [`docs/CALIBRATION.md`](CALIBRATION.md)

## Notation

| Symbol | Meaning | Unit / Range |
|--------|---------|--------------|
| `d` | Layer height (single layer thickness) | mm (typically 0.08) |
| `td_c` | Transmission distance for color `c` | mm (from TD1S or calibrated) |
| `alpha` | Absorption coefficient | dimensionless |
| `F_ch(c)` | Filament RGB value for color `c`, channel `ch` | 0-255 |
| `A_ch(c)` | Per-channel absorption: `(255 - F_ch(c)) / 255` | 0-1 |
| `code` | Layer sequence bottom-to-top, e.g. `"CCMM"` = 4 layers | string of N chars |
| `T` | Transmission rate (fraction of light passing through) | 0-1 |
| `L_i` | Light loss ratio for layer `i` | 0-1, sum to 1 |

## HueForge / Kromacut (Industry Standard)

Reference: [Kromacut source](https://github.com/vycdev/Kromacut/blob/main/src/lib/autoPaint.ts), [HueForge FAQ](https://hueforge.wiki/index.php/FAQ)

HueForge and Kromacut use **base-10** Beer-Lambert with scalar transmission and per-channel linear interpolation.

### Formula

```
T = 10^(-d / TD)                                        [scalar, base-10]

equivalently:
T = exp(-ln(10) * d / TD)                               [alpha = ln(10) ~ 2.3026]
```

Iterative stacking from white background:

```
result = (255, 255, 255)                                 [white]

for each layer c in code:
    opacity = 1 - T_c
    result_ch = F_ch(c) * opacity + result_ch * T_c      [per-channel interpolation]
```

### Single layer on white

```
result_ch = F_ch * (1 - T) + 255 * T
          = 255 - (255 - F_ch) * (1 - T)
          = 255 - A_ch * 255 * (1 - T)
```

Effective opacity: `(1 - T)` — linear in transmission.

### Properties

- Scalar T (same for all RGB channels), per-channel blending via interpolation
- `alpha = ln(10)` is fixed by convention, not calibrated
- TD from TD1S instrument is used directly
- Order-dependent (layer sequence matters)
- Per-channel color mixing comes from `F_ch` in the interpolation, not from T

---

## Mode O: Original

Our baseline model. Uses **natural-base** Beer-Lambert with a **probabilistic light distribution** stacking model.

**Function**: `_code_to_rgb_cached()` in `blend_color.py`

### Transmission

```
T_i = exp(-alpha * d / td_{code[i]})                     [scalar, natural base]
```

### Light distribution (probabilistic)

Instead of sequential filtering, Original distributes the total light budget across all layers probabilistically:

```
remain = 1.0
for i = 0 to N-1:
    L_i = remain * (1 - T_i)          [light absorbed by layer i]
    remain *= T_i                     [light passing through layer i]
L_bg = remain                         [light reaching white backing]

normalize: L_i = L_i / sum(all L)     [so they sum to 1.0]
```

### Final color

```
rgb_ch = 1.0                          [start white, normalized 0-1]
for each layer i:
    rgb_ch -= A_ch(code[i]) * L_i     [subtract each layer's absorption]
                                       A_ch is per-channel, L_i is scalar

final_ch = L_bg * 1.0 + (1 - L_bg) * rgb_ch
output = clip(final_ch * 255, 0, 255)
```

### Single layer on white (derivation of (1-T)^2)

```
L_layer = (1 - T),   L_bg = T,   sum = 1   (no normalization needed)

rgb = 1 - A_ch * (1 - T)

final = L_bg * 1 + (1 - L_bg) * rgb
      = T * 1 + (1 - T) * (1 - A_ch * (1 - T))
      = T + (1 - T) - A_ch * (1 - T)^2
      = 1 - A_ch * (1 - T)^2
```

The `(1-T)^2` effective opacity arises naturally from the probabilistic model. Physically, this models **double-pass light** — light enters the layer, gets partially absorbed, reflects off the white backing, and passes through again.

### Comparison: (1-T)^2 vs (1-T)

For `T = 0.726` (Cyan, single layer, alpha=12, td=3.0):

| | Original | Kromacut |
|---|---|---|
| Effective opacity | `(1-T)^2 = 0.075` | `(1-T) = 0.274` |
| Per-layer absorption | 7.5% | 27.4% |

Original absorbs ~3.6x less per layer. This better matches physical reality — 0.08mm PLA layers are nearly transparent.

### Calibration parameters

| Mode | Parameters | Count |
|------|-----------|-------|
| `alpha` | alpha (td fixed from TD1S) | 1 |
| `alpha_td` | alpha + td per color | 1 + N |

### Properties

- Scalar T (all RGB channels share one transmission per layer)
- Per-channel effect comes only from `A_ch * L_i` at the end
- **Limitation**: Cyan and White with the same td get the same T, even though Cyan selectively absorbs R while White absorbs uniformly

---

## Mode A: Kromacut (our implementation)

Reimplementation of HueForge/Kromacut formula for comparison.

**Function**: `_blend_kromacut()` in `blend_color.py`

### Formula

Identical to HueForge above, using `T = exp(-ln(10) * d / td)`.

Sequential filtering from white:

```
result = (255, 255, 255)
for c in code:
    T = exp(-ln(10) * d / td_c)
    opacity = 1 - T
    result_ch = F_ch(c) * opacity + result_ch * T
```

### Properties

- No `alpha` parameter (fixed at `ln(10)`)
- Linear opacity `(1-T)` vs Original's quadratic `(1-T)^2`
- Overestimates per-layer absorption, especially for thin layers

---

## Mode B: Per-Channel Transmission

Each RGB channel gets its own transmission rate derived from the filament hex color.

**Function**: `_blend_per_channel()` in `blend_color.py`

### Formula

```
A_ch(c) = (255 - F_ch(c)) / 255               [per-channel absorption from hex]
T_ch(c) = exp(-A_ch(c) * d / td_c)            [per-channel transmission]
```

Sequential filtering:

```
result = (255, 255, 255)
for c in code:
    result_ch = F_ch(c) * (1 - T_ch) + result_ch * T_ch
```

### Example: Cyan (#3D79C6)

```
A = (0.76, 0.53, 0.22)     [absorbs R most, B least]

T_R = exp(-0.76 * 0.08 / 3.0) = 0.980     [low R transmission = absorbs R]
T_G = exp(-0.53 * 0.08 / 3.0) = 0.986
T_B = exp(-0.22 * 0.08 / 3.0) = 0.994     [high B transmission = passes B]
```

### Fatal flaw: White is invisible

```
White (#FFFFFF): A = (0, 0, 0)
T_ch = exp(-0 * d / td) = 1.0 for all channels
opacity = 0 -> layer is 100% transparent regardless of thickness
```

White filament has zero per-channel absorption, so the model predicts it's completely transparent. In reality, White PLA scatters light and is semi-opaque. This is why Per-channel mode has the worst dE (13.62 on ramp, 44.01 on 16x16).

---

## Mode H: Hybrid (New)

Combines Original's probabilistic stacking with per-channel transmission. Adds a **base scattering term** to fix the White/Black transparency problem.

**Function**: `_blend_hybrid()` in `blend_color.py`

### Transmission

```
T_ch(i) = exp(-(scatter_alpha / td_c  +  k * A_ch(c)) * d)
              |__________________|     |_______________|
              base scattering          per-channel absorption
              (channel-neutral)        (channel-selective)
```

Two terms in the exponent:
- **`scatter_alpha / td_c`**: Base opacity from material scattering. Same for all RGB channels. Provides opacity for White (A=0) and Black (A~1).
- **`k * A_ch(c)`**: Per-channel selective absorption from pigment. Different per RGB channel. Provides color selectivity for CMY.

### Light distribution (per-channel, Original-style)

Same structure as Original, but `T`, `L`, `remain` are all **3D vectors**:

```
remain_ch = (1, 1, 1)
for i = 0 to N-1:
    L_ch(i) = remain_ch * (1 - T_ch(i))     [per-channel light absorbed]
    remain_ch *= T_ch(i)                     [per-channel remaining light]
L_ch(bg) = remain_ch

normalize per channel: L_ch(i) = L_ch(i) / sum_ch
```

### Final color

```
rgb_ch = 1.0
for each layer i:
    rgb_ch -= A_ch(code[i]) * L_ch(i)        [both are per-channel vectors]

final_ch = L_ch(bg) * 1.0 + (1 - L_ch(bg)) * rgb_ch
```

### Behavior by material type

**White (#FFFFFF, A = (0, 0, 0))**:

```
T_ch = exp(-(scatter_alpha/td + k*0) * d) = exp(-scatter_alpha * d / td)
     = same for R, G, B
     -> degrades to scalar T, identical to Original mode
```

**Black (#0B0F0C, A ~ (0.96, 0.94, 0.95))**:

```
T_ch = exp(-(scatter_alpha/td + k*~0.95) * d)
     ~ same for R, G, B (all A_ch nearly equal)
     -> nearly opaque, approximately channel-neutral
```

**Cyan (#3D79C6, A = (0.76, 0.53, 0.22))**:

```
scatter = scatter_alpha / td = 5.15 / 3.0 = 1.717

T_R = exp(-(1.717 + 17.7*0.76) * 0.08) = exp(-1.214) = 0.297
T_G = exp(-(1.717 + 17.7*0.53) * 0.08) = exp(-0.888) = 0.411
T_B = exp(-(1.717 + 17.7*0.22) * 0.08) = exp(-0.449) = 0.638

T_R < T_G < T_B -> absorbs Red most, passes Blue most = Cyan behavior
```

### Calibration parameters

| Mode | Parameters | Count |
|------|-----------|-------|
| `hybrid` | scatter_alpha + k (td fixed from TD1S) | 2 |
| `hybrid_td` | scatter_alpha + k + td per color | 2 + N |

### Why hybrid works

| Problem | Per-Channel (Mode B) | Hybrid |
|---------|---------------------|--------|
| White is invisible | A=0 -> T=1 -> transparent | scatter_alpha/td provides base opacity |
| Black is invisible | A~1 -> T~0 -> ok | scatter_alpha/td + k*A -> ok |
| Cyan absorbs R | T_R < T_B -> correct | T_R < T_B -> correct |
| Single-td for Cyan | no (uses A directly) | scatter gives base + k*A gives selectivity |

---

## Performance Comparison

### Single-color ramp (4 colors x 4 thicknesses)

| Mode | Optimized dE | Parameters |
|------|-------------|------------|
| **Original** | 3.30 | alpha=41.5, td optimized |
| Kromacut | 3.44 | td optimized |
| Per-channel | 13.62 | td optimized |
| **Hybrid** | **3.01** | scatter_alpha=14.6, k=9.3 |

### Two-color pair ramp (12 pairs x 4 thicknesses)

| Mode | Overall dE | Control (KW/WK) | Selective (CMY) | Mixed (CK/MK/YK) |
|------|-----------|-----------------|-----------------|-------------------|
| Original (alpha_td) | 15.72 | 6.51 | 21.35 | 15.81 |
| Hybrid (scatter+k) | 12.46 | 12.18 | 14.87 | 11.98 |
| **Hybrid_td** | **9.78** | **6.52** | **12.42** | **9.93** |

Hybrid_td achieves 38% improvement over Original on two-color pairs.

### 16x16 permutation plate (256 four-color combinations)

| Mode | Optimized dE |
|------|-------------|
| **Original** | **34.03** |
| Kromacut | 38.68 |
| Per-channel | 44.01 |
| Hybrid | TBD |

### Optimal parameters (hybrid_td, pair ramp)

```
scatter_alpha = 5.15
k             = 17.70
td_C          = 2.06
td_M          = 299.6   (scatter ~ 0, absorption-dominated)
td_Y          = 1.46
td_W          = 1.84
td_K          = 0.1     (instrument floor)
```

## Evolution

```
Original (scalar T, probabilistic stacking)
    |
    |-- good single-color (dE=3.30)
    |-- poor multi-color (dE=34.03)
    |-- root cause: scalar T can't model per-channel absorption
    |
    v
Hybrid (per-channel T, probabilistic stacking)
    |
    |-- scatter_alpha/td provides base opacity (fixes White/Black)
    |-- k*A_ch provides per-channel selectivity (fixes CMY)
    |-- preserves (1-T)^2 double-pass physics
    |-- single-color: dE=3.01 (better)
    |-- two-color: dE=9.78 (38% better)
    |
    v
Next: validate on 16x16 plate, then promote to production
```
