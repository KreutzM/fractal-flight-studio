# Double-Single perturbation research benchmark

This isolated benchmark evaluates whether the native FP64 arithmetic in the CUDA Mandelbrot perturbation delta recurrence can be replaced by FP32 double-single arithmetic.

It does **not** change the production perturbation renderer or routing policy.

## Scope

The existing CPU architecture remains intact:

- the reference orbit is constructed at arbitrary precision on the CPU;
- reference selection, re-anchoring and the configured precision budget remain unchanged;
- the benchmark transfers the same reference orbit either as two FP64 arrays or as four FP32 `(hi, lo)` arrays;
- only the GPU delta recurrence, escape checks, glitch checks and rebasing arithmetic are compared.

The four FP32 orbit arrays require the same number of transfer bytes as the two FP64 arrays. The experiment therefore isolates arithmetic throughput and represented precision rather than reducing orbit bandwidth.

## Variants

1. the existing native FP64 production perturbation kernel;
2. a research Double-Single kernel using compensated FP32 addition, multiplication, squaring and complex products.

The Double-Single variant uses full represented magnitudes for escape, glitch and rebase decisions. Smooth coloring is derived from the high magnitude component, matching the direct Double-Single research approach.

## Default physical test

The default request uses the validated transition target:

- center `(-0.743643887037151, 0.13182590420533)`;
- view width `5e-13`;
- 1280×720 pixels;
- 1200 iterations;
- 384-bit CPU reference orbit.

Run on Windows from the repository root:

```powershell
.\scripts\benchmark_double_single_perturbation.ps1
```

The command writes `double-single-perturbation-results.json`.

## Reported gates

The report includes:

- sustained CUDA-event kernel timings after duration-based warm-up;
- physical registers, local memory and occupancy information where supported;
- PTX checks for explicit FP32 FMA and unexpected FP64 arithmetic;
- reference-orbit transfer sizes and split reconstruction error;
- inside-mask, normalized-value, glitch-flag and rebase-flag differences against native FP64;
- GPU clock and P-state snapshots.

A production follow-on should proceed only if Double-Single is materially faster, contains no unintended FP64 arithmetic or spilling, and preserves acceptable glitch/rebase behavior across several deep targets. Much deeper zooms will still require a scaled or exponent-separated representation because Double-Single does not extend the FP32 exponent range.
