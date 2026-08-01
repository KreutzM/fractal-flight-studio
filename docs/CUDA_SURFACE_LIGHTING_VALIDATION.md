# CUDA surface-lighting validation

This pull request keeps the 2.5D surface-lighting operation on the CUDA device after tone mapping and palette lookup. Before merge, run the physical validation on the target RTX 3060 from an environment with the project installed:

```powershell
.\.venv\Scripts\python.exe scripts\check_cuda_surface_lighting.py --output surface-lighting-rtx3060.json
```

The command validates direct FP32, guarded direct Double-Single and guarded Double-Single perturbation routes. For every case it compares the GPU-lit RGB frame with the renderer-independent reference post-process, confirms that disabled lighting is byte-identical to the unlit frame, verifies the optimized single-RGB-readback contract and records median lit versus unlit frame times.

Merge criteria:

- the report-level `passed` field is `true`;
- every case reports `maximum_channel_delta <= 1`;
- every case preserves the expected arithmetic and render-mode route;
- disabled lighting matches the baseline exactly;
- the transfer description remains `single RGB readback`;
- no severe or unexplained frame-time regression is observed.

The generated JSON is a machine-readable validation artifact. It is intentionally not committed before a physical run because simulator timing is not representative of GPU execution.
