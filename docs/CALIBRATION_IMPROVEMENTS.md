# Calibration Improvement Proposals

**Date**: 2026-03-10
**Status**: Proposal A implemented, initial k_rgb values need optimization

## Executive Summary

Current best model (P6 Phase6) achieves **dE=39.69** on 16×16 real plate (vs P0 baseline 42.90). Proposal A (per-channel k) was implemented as P7 preset, achieving **dE=39.38** on 16×16 real but performing worse on other photos (Ph1, Ph2, Ph6). The k_rgb values need calibration optimization.

### Bug Fix (2026-03-10)

Fixed missing `k_rgb_map` parameter in `RampCalibrator`:
- `_build_color_map`: Added `k_rgb_map` parameter, passes `k_rgb` to `Color` constructor
- `_predict_rgb`: Added `k_rgb_map` parameter
- `_compute_errors`: Added `k_rgb_map` parameter

This fix enables the `hybrid_per_channel_k` blend mode to work correctly in cross-validation.

## Key Findings

### 1. Per-Channel Scattering is Critical

Current `k` values are color-level averages. Error analysis shows:

| Color | k_avg | R behavior | G behavior | B behavior |
|-------|-------|------------|------------|------------|
| Cyan | 8.13 | **Reflects** (anomalous) | Absorbs | Absorbs |
| Magenta | 8.42 | Weak absorption | **Strong absorption** | Moderate |
| Yellow | 3.73 | **Reflects** | Weak absorption | Strong absorption |

**Implication**: A single `k` cannot capture channel-selective behavior. Per-channel k values (k_R, k_G, k_B) would improve accuracy.

### 2. Cyan is the Primary Error Source

| Code | dE | R error | G error | B error |
|------|-----|---------|---------|---------|
| C | 92.2 | **-101** | -70 | +107 |
| CM | 71.1 | +12 | **-66** | -52 |
| CY | 24.0 | -43 | -6 | +58 |

**Pattern**: Cyan's R channel behaves opposite to Beer-Lambert prediction. Instead of absorbing, it reflects/scatters.

### 3. G Channel Has Systematic Bias

- Mean pred - actual = **-45.3**
- Present in almost all multi-color combinations
- Suggests G transmission is under-estimated globally

### 4. Layer Order Effect

| Forward | Reversed | Ratio |
|---------|----------|-------|
| CM (10.3) | MC (19.8) | 1.9× |
| CY (23.7) | YC (25.0) | 1.1× |
| CMY (14.3) | YMC (26.0) | 1.8× |

More absorptive color on bottom consistently gives lower error.

## Proposed Model Improvements

### Proposal A: Per-Channel k Values

**Change**: Replace single `k` with `k_rgb = (k_R, k_G, k_B)`

**Formula Update**:
```python
# Current
scatter = scatter_alpha / td
absorption = color.get_absorption()  # (A_R, A_G, A_B)
t_ch = exp(-(scatter + k * absorption) * layer_height)

# Proposed
scatter = scatter_alpha / td
absorption = color.get_absorption()  # (A_R, A_G, A_B)
k_per_ch = color.k_rgb  # (k_R, k_G, k_B)
scatter_per_ch = scatter + k_per_ch * absorption
t_ch = exp(-scatter_per_ch * layer_height)
```

**Expected Impact**: Captures Cyan's R-reflection (k_R < 0?) and Yellow's B-dominance (k_B >> k_R)

### Proposal B: Cyan R-Channel Compensation

**Change**: Add explicit reflection term for colors that reflect in certain channels

**Formula Update**:
```python
# For colors with negative absorption (reflection)
reflection = color.get_reflection()  # (R_R, R_G, R_B), e.g., Cyan: (0.3, 0, 0)
t_ch = exp(-(scatter + k * absorption) * layer_height)
# Add reflected light from background
rgb_contribution = t_ch + (1 - t_ch) * reflection
```

**Expected Impact**: Reduces Cyan R error from -101 to near zero

### Proposal C: Channel-Weighted Background Model

**Change**: Use channel-specific background contribution

**Current Issue**: Background RGB is uniformly weighted. But Yellow on white paper appears different than Yellow on black backing in R vs B channels.

**Formula Update**:
```python
# Channel-specific background contribution
bg_contribution = background * channel_weight
# where channel_weight = f(color, channel)
```

**Expected Impact**: Better handles Yellow anomaly (R reflects more than background)

### Proposal D: Optimized Layer Ordering

**Change**: Add post-processing step to reorder layers for minimum error

**Algorithm**:
1. For each target color, compute prediction for all valid layer permutations
2. Select permutation with minimum dE
3. Report ordering to slicer settings

**Expected Impact**: CM→MC swap gives 1.9× improvement; automating this could significantly reduce average error

## Recommended Implementation Order

1. **Immediate**: ~~Implement Proposal A (per-channel k)~~ - DONE, but needs k_rgb value optimization
2. **Short-term**: Implement Proposal D (layer ordering) - easy win, no model changes
3. **Medium-term**: Investigate Proposal B (Cyan compensation) - requires physical validation
4. **Long-term**: Consider Proposal C (channel-weighted background) - complex, may need more data

## Proposal A: P7 Per-Channel k Results (2026-03-10)

### Implementation

- Added `BAMBU_CMYK_PER_CHANNEL_K_PRESET` in `color_config.py`
- Added `hybrid_per_channel_k` blend mode in `blend_models.py`
- Fixed `RampCalibrator` to pass `k_rgb` to `Color` constructor

### Initial k_rgb Values (Guessed)

| Color | k_R | k_G | k_B | Rationale |
|-------|-----|-----|-----|-----------|
| Cyan | 2.0 | 10.0 | 12.0 | R reflects (low), G/B absorb |
| Magenta | 8.0 | 15.0 | 6.0 | G absorbs strongly |
| Yellow | 1.0 | 2.0 | 10.0 | B absorbs, R/G reflect |
| White | 12.39 | 12.39 | 12.39 | Uniform TiO₂ scattering |
| Key | 17.65 | 17.65 | 17.65 | Near-perfect opacity |

### Cross-Validation Results

| Photo | P0 Default | P6 Phase6 | P7 Per-Channel k |
|-------|------------|-----------|------------------|
| Ph1 (Ramp 4x5) | 22.78 | **12.72** | 14.31 |
| Ph2 (Pair 12x4) | 19.75 | **14.46** | 19.23 |
| Ph4 (16x16 synth) | **39.80** | 46.85 | 59.27 |
| Ph5 (16x16 real) | 42.90 | 39.69 | **39.38** |
| Ph6 (MC ramp 12x5) | 22.99 | **15.70** | 21.23 |

### Analysis

- **P7 wins only on Ph5 (16x16 real)**: 39.38 vs 39.69 (P6), marginal improvement
- **P7 is worse on all other photos**: Overfitting to the guessed k_rgb values
- **P0 still best on Ph4 (16x16 synth)**: Original mode with production parameters

### Conclusion

The guessed k_rgb values are not optimal. Proper optimization requires:
1. Running gradient descent on k_rgb parameters
2. Using multiple photos as training data
3. Validating on held-out photos

For now, **P6 Phase6 remains the recommended preset** as it generalizes better across all photos.

## k_rgb Optimizer Implementation (2026-03-10) ✅

### Implementation Complete

The k_rgb optimizer has been implemented with the following changes:

1. **`_objective_hybrid_per_channel_k()`** in `ramp_calibrator.py`:
   - Optimizes scatter_alpha + per-color per-channel k_rgb values
   - Parameter layout: `[scatter_alpha, C_R, C_G, C_B, M_R, M_G, M_B, Y_R, Y_G, Y_B, W_R, W_G, W_B, K_R, K_G, K_B]`
   - For 5 colors (CMYWK): 1 + 3×5 = 16 parameters

2. **`RampCalibrationConfig.k_rgb_bounds`**: Configurable bounds for k_rgb optimization
   - Default: `(0.5, 30.0)` - wider than scalar k bounds to allow negative values for reflection modeling

3. **`RampCalibrationResult.optimal_k_rgb_map`**: Stores optimized k_rgb values in result

4. **Optimization path in `run()`**: Detects `hybrid_per_channel_k` blend mode and uses dedicated optimizer

### Usage

```bash
cd backend
source .venv/bin/activate

# Run k_rgb optimization on a photo
python -m tools.calibration.run_ramp_calibration \
  --photo tools/calibration/photos/IMG_7872_cropped.png \
  --preset bambu \
  --blend-mode hybrid_per_channel_k
```

### Cross-Validation Results (Pre-Optimization)

With guessed k_rgb values:

| Photo | P0 Default | P6 Phase6 | P7 Per-Channel k |
|-------|------------|-----------|------------------|
| Ph1 (Ramp 4x5) | 22.78 | **12.72** | 14.31 |
| Ph2 (Pair 12x4) | — | **14.46** | 19.23 |
| Ph4 (16x16 synth) | **39.80** | 46.85 | 59.27 |
| Ph5 (16x16 real) | 42.90 | 39.69 | **39.38** |
| Ph6 (MC ramp 12x5) | 22.99 | **15.70** | 21.23 |

P7 wins only on Ph5, but is worse on transfer (31.83 vs 28.57).

### Next Steps

1. Run k_rgb optimizer on training photos (Ph1 + Ph2 + Ph6)
2. Validate optimized k_rgb on held-out photo (Ph5)
3. Add k_rgb regularization to prevent overfitting

## Original Implementation Requirements (Archived)

The following requirements were documented before implementation:

With proper optimization, P7 could potentially:
- Reduce Ph5 from 39.38 to ~35 (based on P0c results)
- Maintain good transfer to Ph6 (target: <20)

## Latest Cross-Validation Results (2026-03-10)

### Full Parameter Set Comparison

| Preset | Ph1 | Ph2 | Ph4 | Ph5 | Ph6 | Transfer |
|--------|-----|-----|-----|-----|-----|----------|
| **P0 Default** | 22.78 | — | **39.80** | 42.90 | 22.99 | 35.02 |
| P0b TD1S α=12 | 27.25 | — | 39.31 | 44.69 | 26.89 | 37.39 |
| P0c TD1S ln10 | 48.95 | — | 31.93 | **37.44** | 51.29 | 41.65 |
| P1 Ramp best | **3.30** | — | 68.27 | 67.97 | 24.50 | 49.06 |
| P3 Hybrid | 8.30 | — | 53.53 | 40.13 | 11.94 | 30.78 |
| P4 Hybrid_td | 7.29 | **9.78** | 44.03 | 39.03 | **10.62** | **25.62** |
| **P6 Phase6** | 12.72 | 14.46 | 46.85 | 39.69 | 15.70 | 28.57 |
| P7 Per-ch k | 14.31 | 19.23 | 59.27 | 39.38 | 21.23 | 31.83 |

### Ranking by Transfer Score (Best Generalization)

1. **P4 Hybrid_td**: 25.62 (best transfer, good Ph5=39.03)
2. **P6 Phase6**: 28.57 (balanced, recommended production preset)
3. P3 Hybrid: 30.78
4. P7 Per-ch k: 31.83 (overfits to Ph5)
5. P0 Default: 35.02 (safest baseline)

### Recommendations

1. **Production**: Use **P6 Phase6** - best balance of accuracy and generalization
2. **Single-color**: Use **P4 Hybrid_td** - excellent transfer for limited color mixing
3. **Future work**: Implement k_rgb optimizer to improve P7's generalization

## References

- Error analysis: `tools/calibration/results/20260224_125726_error_analysis/`
- Cross-validation: `tools/calibration/results/20260310_085528_cross_validation/`
- Model search: `tools/calibration/results/20260307_025037_model_search/`
