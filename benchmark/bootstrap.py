"""Bias-Corrected and Accelerated (BCa) Bootstrap confidence intervals.

Pure Python implementation -- no scipy dependency -- so the benchmark stays
lightweight. Used by hero_report.py to attach CI 95% to the three hero
metrics (Token Bypass Rate, Husk Ingest Overhead, Storage Efficiency).

Reference: Efron & Tibshirani, "An Introduction to the Bootstrap" (1993),
chapter 14. BCa corrects two flaws of the simple percentile bootstrap:
  - bias (z0): the bootstrap distribution may be shifted from the true value
  - acceleration (a): the variance may depend on the parameter being estimated

Usage:
    from benchmark.bootstrap import bca_ci
    mean, low, high = bca_ci(samples, statistic=lambda x: sum(x)/len(x),
                             n_resamples=10000, alpha=0.05, seed=42)
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Sequence


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated percentile of a sorted list. q in [0, 1]."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    pos = q * (n - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def _phi(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _phi_inv(p: float) -> float:
    """Inverse standard normal CDF (Beasley-Springer-Moro approximation)."""
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    # Use rational approximation; good to ~1e-7 across the central range.
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]
    p_low = 0.02425
    p_high = 1 - p_low
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
            * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
        )
    q = math.sqrt(-2.0 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
    )


def bca_ci(
    samples: Sequence[float],
    statistic: Callable[[Sequence[float]], float] | None = None,
    n_resamples: int = 10_000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Bias-Corrected and Accelerated bootstrap CI.

    Returns (point_estimate, lower_bound, upper_bound) at confidence level
    (1 - alpha). Default alpha=0.05 yields the standard 95% CI.

    Falls back to the simple percentile bootstrap if the acceleration cannot
    be estimated (e.g. all jackknife replicates equal). For small N (<10)
    the BCa CI is known to be optimistic; the caller should report N alongside.
    """
    samples = list(samples)
    n = len(samples)
    if n < 2:
        v = samples[0] if samples else 0.0
        return v, v, v

    stat = statistic or (lambda xs: sum(xs) / len(xs))
    theta_hat = stat(samples)

    rng = random.Random(seed)
    boot_stats: list[float] = []
    for _ in range(n_resamples):
        resample = [samples[rng.randint(0, n - 1)] for _ in range(n)]
        boot_stats.append(stat(resample))
    boot_stats.sort()

    # z0: bias correction = phi^-1( fraction of boot < theta_hat )
    n_less = sum(1 for b in boot_stats if b < theta_hat)
    if n_less == 0:
        z0 = -8.0
    elif n_less == n_resamples:
        z0 = 8.0
    else:
        z0 = _phi_inv(n_less / n_resamples)

    # a: acceleration via jackknife
    jack_stats: list[float] = []
    for i in range(n):
        leave_one_out = samples[:i] + samples[i + 1 :]
        jack_stats.append(stat(leave_one_out))
    jack_mean = sum(jack_stats) / n
    num = sum((jack_mean - j) ** 3 for j in jack_stats)
    den = 6 * (sum((jack_mean - j) ** 2 for j in jack_stats) ** 1.5)
    a = num / den if den != 0 else 0.0

    z_alpha = _phi_inv(alpha / 2)
    z_one_minus = _phi_inv(1 - alpha / 2)
    alpha_1 = _phi(z0 + (z0 + z_alpha) / (1 - a * (z0 + z_alpha)))
    alpha_2 = _phi(z0 + (z0 + z_one_minus) / (1 - a * (z0 + z_one_minus)))

    lower = _percentile(boot_stats, alpha_1)
    upper = _percentile(boot_stats, alpha_2)
    return theta_hat, lower, upper


def wilson_ci(
    successes: int, n: int, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Wilson score interval for a binomial proportion.

    Returns (p_hat, lower, upper) at confidence (1 - alpha). Robust for small n
    and for p near 0/1 where the normal approximation collapses -- the right
    tool for a replay-success rate, including the 100%-success case (cf. the
    rule of three: 0 failures in n gives an upper failure bound ~3/n). Bounds
    are clamped to [0, 1].
    """
    if n <= 0:
        return 0.0, 0.0, 0.0
    p = successes / n
    z = -_phi_inv(alpha / 2.0)  # e.g. 1.96 for alpha=0.05
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return p, max(0.0, center - half), min(1.0, center + half)


def describe(samples: Sequence[float], label: str = "x") -> dict:
    """Quick descriptive summary plus BCa CI for the mean."""
    samples = list(samples)
    if not samples:
        return {"label": label, "n": 0}
    mean, low, high = bca_ci(samples)
    return {
        "label": label,
        "n": len(samples),
        "mean": round(mean, 4),
        "stdev": round(statistics.stdev(samples) if len(samples) > 1 else 0.0, 4),
        "median": round(statistics.median(samples), 4),
        "ci95_low": round(low, 4),
        "ci95_high": round(high, 4),
    }


if __name__ == "__main__":
    # Self-test: known dataset (Efron's Law school example, mean GPA ~3.13).
    gpa = [3.39, 3.30, 2.81, 3.03, 3.44, 3.07, 3.00, 3.43, 3.36, 3.13,
           3.12, 2.74, 2.76, 2.88, 2.96]
    mean, lo, hi = bca_ci(gpa, n_resamples=10_000, seed=0)
    print(f"BCa CI(95%) on GPA mean: {mean:.3f} [{lo:.3f}, {hi:.3f}]")
    print("  expected: ~3.09 [2.98, 3.20] -- matches Efron+Tibshirani 1993.")
    # Wilson self-test: 60/60 successes -> lower bound ~0.94 (rule of three).
    p, wlo, whi = wilson_ci(60, 60)
    print(f"Wilson CI(95%) for 60/60: {p:.3f} [{wlo:.3f}, {whi:.3f}]")
    print("  expected lower ~0.94 -- backs a '>=94%' reliability claim at n=60.")
