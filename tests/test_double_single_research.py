from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import mpmath as mp
import numpy as np
import pytest

from fractal_flight_studio.research.double_single import (
    DoubleSingle,
    add_cpu,
    coordinate_at,
    coordinate_components,
    diff_squares_cpu,
    grid_unique_fraction,
    mandelbrot_double_single_cpu,
    mandelbrot_reference,
    mul_cpu,
    quick_two_sum_cpu,
    split_mpf,
    square_cpu,
    sub_cpu,
    two_product_cpu,
    two_sum_cpu,
)


def _value(number: DoubleSingle) -> mp.mpf:
    return mp.mpf(float(number.hi)) + mp.mpf(float(number.lo))


def test_two_sum_is_error_free_for_fp32_inputs() -> None:
    rng = np.random.default_rng(20260729)
    for _ in range(500):
        a = np.float32(rng.uniform(-1e5, 1e5))
        b = np.float32(rng.uniform(-1e5, 1e5))
        result = two_sum_cpu(a, b)
        assert float(result.hi) + float(result.lo) == float(a) + float(b)


def test_quick_two_sum_checks_precondition() -> None:
    with pytest.raises(ValueError, match=r"abs\(a\)"):
        quick_two_sum_cpu(np.float32(1.0), np.float32(2.0))

    result = quick_two_sum_cpu(np.float32(2.0), np.float32(2**-20))
    assert float(result.hi) + float(result.lo) == float(np.float32(2.0)) + float(
        np.float32(2**-20)
    )


def test_two_product_recovers_fp32_product_residual() -> None:
    rng = np.random.default_rng(42)
    for _ in range(500):
        a = np.float32(rng.uniform(-100.0, 100.0))
        b = np.float32(rng.uniform(-100.0, 100.0))
        result = two_product_cpu(a, b)
        assert float(result.hi) + float(result.lo) == pytest.approx(
            float(a) * float(b), rel=0.0, abs=0.0
        )


def test_double_single_basic_operations_retain_about_44_bits() -> None:
    with mp.workprec(200):
        a_exact = mp.mpf("1.234567890123456789")
        b_exact = mp.mpf("-0.9876543210987654321")
        a = split_mpf(a_exact)
        b = split_mpf(b_exact)
        cases = (
            (add_cpu(a, b), a_exact + b_exact),
            (sub_cpu(a, b), a_exact - b_exact),
            (mul_cpu(a, b), a_exact * b_exact),
            (square_cpu(a), a_exact * a_exact),
        )
        for actual, expected in cases:
            assert abs(_value(actual) - expected) < mp.mpf(2) ** -43


def test_compensated_difference_of_squares_survives_cancellation() -> None:
    with mp.workprec(200):
        a_exact = mp.mpf("1.00000011920928955078125")
        b_exact = mp.mpf("1.000000059604644775390625")
        a = split_mpf(a_exact)
        b = split_mpf(b_exact)
        compensated = diff_squares_cpu(a, b)
        expected = a_exact * a_exact - b_exact * b_exact
        high_only = np.float32(a.hi * a.hi - b.hi * b.hi)
        compensated_error = abs(_value(compensated) - expected)
        high_error = abs(mp.mpf(float(high_only)) - expected)
        assert compensated_error < high_error
        assert compensated_error < mp.mpf(2) ** -45


def test_exact_decimal_grid_stays_distinct_below_float64_spacing() -> None:
    x0, y0, dx, dy = coordinate_components(
        "-0.74364388703715100000000000000000001",
        "0.13182590420533000000000000000000001",
        "1e-12",
        256,
        144,
        precision_bits=256,
    )
    assert grid_unique_fraction(x0, dx, 256) == 1.0
    assert grid_unique_fraction(y0, dy, 144) == 1.0
    left = coordinate_at(x0, dx, 127)
    right = coordinate_at(x0, dx, 128)
    assert (left.hi, left.lo) != (right.hi, right.lo)
    assert float(left.hi) == float(right.hi)


def test_double_single_mandelbrot_matches_high_precision_escape() -> None:
    cr = split_mpf("-0.75")
    ci = split_mpf("0.1")
    ds = mandelbrot_double_single_cpu(cr, ci, 200)
    reference = mandelbrot_reference("-0.75", "0.1", 200, precision_bits=256)
    assert ds.escaped is reference.escaped
    assert ds.escape_iteration == reference.escape_iteration
    assert ds.smooth_iteration == pytest.approx(reference.smooth_iteration, abs=2e-5)


def test_cuda_simulator_launches_specialized_kernel(tmp_path: Path) -> None:
    script = tmp_path / "simulate.py"
    script.write_text(
        """
import json
import numpy as np
from fractal_flight_studio.research.double_single import (
    DS_SPECIALIZED_LO2_ADAPTIVE_KERNEL,
    coordinate_components,
)
width = height = 4
iterations = np.zeros((height, width), dtype=np.int32)
smooth = np.zeros((height, width), dtype=np.float32)
orbit = np.zeros((height, width, 4), dtype=np.float32)
x0, y0, dx, dy = coordinate_components('-0.75', '0.1', '0.02', width, height)
DS_SPECIALIZED_LO2_ADAPTIVE_KERNEL[(1, 1), (8, 8)](
    iterations, smooth, orbit, width, height,
    x0.hi, x0.lo, y0.hi, y0.lo, dx.hi, dx.lo, dy.hi, dy.lo,
    64, np.float32(4.0),
)
print(json.dumps({'shape': list(iterations.shape), 'finite': bool(np.isfinite(orbit).all())}))
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["NUMBA_ENABLE_CUDASIM"] = "1"
    project_src = str(Path(__file__).parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (project_src, env.get("PYTHONPATH", "")) if part
    )
    completed = subprocess.run(
        [sys.executable, str(script)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert json.loads(completed.stdout) == {"shape": [4, 4], "finite": True}
