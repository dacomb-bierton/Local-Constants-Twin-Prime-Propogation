"""Minimal productive gaps ``d(t)`` for every lower twin ``t <= X``.

``d`` is a productive gap for ``t in T`` when ``t + d in T``,
``2t + d + 1 in T`` and ``d - 1`` or ``d + 1`` is prime.  For ``t > 3`` every
productive gap is ``0 (mod 6)``; ``t = 3`` has no productive gap at all
(``3 + d in T`` forces ``d = 2 (mod 6)`` and then ``2*3 + d + 1 = 0 (mod 3)``).

The refined conjecture (Conjecture B' in ``REFINED_CONJECTURES.md``) replaces
``d(t) = o(t)`` with

    d(t) <= (log t)^5 * log log t * K            for all t in T, t >= 5,

and predicts the typical size ``(log t)^4 log log t``.  This module computes
``d(t)`` exactly, records the running maxima, and compares block means with
the Bateman-Horn model built from the singular series in :mod:`local`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .local import SingularSeries, gap_series
from .sieve import lower_twins, prime_table


@dataclass
class GapBlock:
    lo: int
    hi: int
    count: int
    mean_d: float
    median_d: float
    max_d: int
    argmax_t: int
    mean_norm4: float  # mean of d / ((log t)^4 log log t)
    max_norm5: float  # max of d / ((log t)^5 log log t)
    model_mean: float = float("nan")
    model_samples: int = 0

    @property
    def mean_ratio(self) -> float:
        return self.mean_d / self.model_mean if self.model_mean else float("nan")


@dataclass
class GapResult:
    limit: int
    cap: int
    t: np.ndarray
    d: np.ndarray
    side_minus: np.ndarray  # d-1 prime
    side_plus: np.ndarray  # d+1 prime
    missing: list[int]
    records: list[tuple[int, int, float]] = field(default_factory=list)  # (t, d, d/((log t)^5 loglog t))
    blocks: list[GapBlock] = field(default_factory=list)

    @property
    def n(self) -> int:
        return int(len(self.t))


def _norm4(t: np.ndarray) -> np.ndarray:
    # log log t is clipped at 1 (i.e. log t >= e) so that the tiny twins
    # t = 5, 11 do not produce negative or explosive normalisations.
    lt = np.log(t.astype(float))
    return lt**4 * np.log(np.maximum(lt, math.e))


def _norm5(t: np.ndarray) -> np.ndarray:
    lt = np.log(t.astype(float))
    return lt**5 * np.log(np.maximum(lt, math.e))


def minimal_productive_gaps(limit: int, cap: int = 1 << 25,
                            first_window: int = 512) -> GapResult:
    """Exact ``d(t)`` for every ``t in T`` with ``5 <= t <= limit``.

    ``cap`` bounds the search; any ``t`` without a productive gap ``<= cap``
    is reported in ``missing`` (none are expected: ``cap`` is far above the
    conjectured ``(log t)^5 log log t`` scale for the ranges this handles).
    """
    limit = int(limit)
    cap = int(cap) - (int(cap) % 6)
    table_limit = 2 * limit + cap + 8
    is_p = prime_table(table_limit)
    tw = is_p[:-2] & is_p[2:]
    twins = lower_twins(is_p, limit)
    twins = twins[twins >= 5]

    d_grid = np.arange(6, cap + 1, 6, dtype=np.int64)
    side_minus_grid = is_p[d_grid - 1]
    side_plus_grid = is_p[d_grid + 1]
    side_grid = side_minus_grid | side_plus_grid

    d_out = np.zeros(len(twins), dtype=np.int64)
    missing: list[int] = []
    for i, t in enumerate(twins):
        t = int(t)
        w = first_window
        lo = 0
        found = -1
        while lo < len(d_grid):
            hi = min(lo + w, len(d_grid))
            dd = d_grid[lo:hi]
            ok = tw[t + dd] & tw[2 * t + 1 + dd] & side_grid[lo:hi]
            j = np.flatnonzero(ok)
            if len(j):
                found = int(dd[j[0]])
                break
            lo = hi
            w *= 2
        if found < 0:
            missing.append(t)
        d_out[i] = found

    keep = d_out > 0
    t_arr = twins[keep]
    d_arr = d_out[keep]
    res = GapResult(
        limit=limit,
        cap=cap,
        t=t_arr,
        d=d_arr,
        side_minus=is_p[d_arr - 1],
        side_plus=is_p[d_arr + 1],
        missing=missing,
    )

    # running maxima
    best = -1
    n5 = d_arr / _norm5(t_arr)
    for i in range(len(t_arr)):
        if d_arr[i] > best:
            best = int(d_arr[i])
            res.records.append((int(t_arr[i]), best, float(n5[i])))

    # dyadic blocks
    k = np.floor(np.log2(t_arr)).astype(int)
    n4 = d_arr / _norm4(t_arr)
    for kk in range(int(k.min()), int(k.max()) + 1):
        m = k == kk
        if not m.any():
            continue
        dm = d_arr[m]
        tm = t_arr[m]
        am = int(np.argmax(dm))
        res.blocks.append(
            GapBlock(
                lo=1 << kk,
                hi=1 << (kk + 1),
                count=int(m.sum()),
                mean_d=float(dm.mean()),
                median_d=float(np.median(dm)),
                max_d=int(dm[am]),
                argmax_t=int(tm[am]),
                mean_norm4=float(n4[m].mean()),
                max_norm5=float(n5[m].max()),
            )
        )
    return res


# --------------------------------------------------------------------------
# Bateman-Horn model for the distribution of d(t)
# --------------------------------------------------------------------------

def expected_count_curve(t: int, ss: SingularSeries, Y: int,
                         max_points: int = 4_000_000) -> tuple[np.ndarray, np.ndarray]:
    """``(d_grid, E_t(d_grid))``: the Bateman-Horn expectation of the number
    of productive gaps ``<= d`` at ``t``, on the grid ``d = 6m, 12m, ...``
    with ``m = 1`` unless ``Y/6 > max_points`` (then the density, which
    varies only through ``log d``, is taken constant on blocks of ``m``
    admissible gaps).

    Probability that a given ``d = 0 (mod 6)`` is productive:

        6 * A(d) * [ S^-(t)/log(d-1) + S^+(t)/log(d+1) - S^6(t)/(log(d-1) log(d+1)) ],

    ``A(d) = 1/(log(t+d) log(t+d+2) log(2t+d+1) log(2t+d+3))``.  The factor 6
    converts the density over all integers ``d`` into the density over the
    admissible class ``d = 0 (mod 6)``.
    """
    s_minus, s_plus, s_both = gap_series(t, ss)
    m = max(1, -(-(Y // 6) // max_points))
    step = 6 * m
    d = np.arange(step, Y + 1, step, dtype=float)
    if t < 10**300:
        tf = float(t)
        A = 1.0 / (np.log(tf + d) * np.log(tf + d + 2) * np.log(2 * tf + d + 1) * np.log(2 * tf + d + 3))
    else:
        # beyond double range: log(a t + d + b) = log t + log a + log1p((d + b) / (a t)),
        # and (d + b) / t underflows harmlessly to 0 when d << t
        lt = math.log(t)
        inv_t = math.exp(-lt) if lt < 700 else 0.0
        l1 = lt + np.log1p(d * inv_t)
        l2 = lt + np.log1p((d + 2) * inv_t)
        l3 = lt + math.log(2) + np.log1p((d + 1) * inv_t / 2)
        l4 = lt + math.log(2) + np.log1p((d + 3) * inv_t / 2)
        A = 1.0 / (l1 * l2 * l3 * l4)
    lm = np.log(np.maximum(d - 1, 2.0))
    lp = np.log(d + 1)
    prob = 6.0 * A * (s_minus / lm + s_plus / lp - s_both / (lm * lp))
    return d, np.cumsum(prob) * m


def model_survival(t: int, ss: SingularSeries, d_obs: int) -> tuple[float, float]:
    """``(E_t(d_obs), P(d(t) > d_obs) = exp(-E_t(d_obs)))`` in the Poisson
    model.  Over many independent ``t`` the second value should be uniform
    on ``(0, 1)``."""
    _, E = expected_count_curve(t, ss, max(int(d_obs), 6))
    e = float(E[-1]) if len(E) else 0.0
    return e, math.exp(-e)


def model_expected_min_gap(t: int, ss: SingularSeries, Y: int | None = None) -> float:
    """``E[d(t)]`` in the Poisson model ``P(d(t) > Y) = exp(-E_t(Y))``, i.e.
    ``sum over the grid of step * exp(-E_t(d))`` (plus the first step)."""
    if Y is None:
        lt = math.log(t)
        Y = int(max(20_000, 60 * lt**4 * math.log(max(lt, math.e))))
        Y -= Y % 6
    d, E = expected_count_curve(t, ss, Y)
    step = float(d[1] - d[0]) if len(d) > 1 else 6.0
    tail = np.exp(-E)
    return step * (1.0 + float(tail.sum()))


def attach_model(res: GapResult, ss: SingularSeries | None = None,
                 samples_per_block: int = 150, seed: int = 1) -> None:
    """Fill ``model_mean`` of every block from a random subsample of its
    twins."""
    ss = ss or SingularSeries()
    rng = np.random.default_rng(seed)
    k = np.floor(np.log2(res.t)).astype(int)
    for blk in res.blocks:
        idx = np.flatnonzero(k == int(math.log2(blk.lo)))
        if len(idx) > samples_per_block:
            idx = rng.choice(idx, samples_per_block, replace=False)
        vals = [model_expected_min_gap(int(res.t[i]), ss) for i in idx]
        blk.model_mean = float(np.mean(vals)) if vals else float("nan")
        blk.model_samples = len(vals)


def format_report(res: GapResult) -> str:
    L = []
    L.append(f"Minimal productive gaps d(t), 5 <= t <= {res.limit:,}  (search cap {res.cap:,})")
    L.append(f"  twins examined         : {res.n:,}")
    L.append(f"  twins without a gap    : {len(res.missing)}  {res.missing[:10]}")
    L.append(f"  max d(t)               : {int(res.d.max()):,} at t = {int(res.t[np.argmax(res.d)]):,}")
    frac_minus_only = float(np.mean(res.side_minus & ~res.side_plus))
    frac_plus_only = float(np.mean(res.side_plus & ~res.side_minus))
    frac_both = float(np.mean(res.side_minus & res.side_plus))
    L.append(f"  side condition at d(t) : d-1 only {frac_minus_only:.3f}, d+1 only {frac_plus_only:.3f}, both {frac_both:.3f}")
    L.append("")
    L.append("  block [lo,hi)     count     mean d   median d      max d     at t          mean d/((ln t)^4 lnln t)  max d/((ln t)^5 lnln t)  model mean  mean/model")
    for b in res.blocks:
        L.append(
            f"  [2^{int(math.log2(b.lo)):2d},2^{int(math.log2(b.hi)):2d})  {b.count:8,d} {b.mean_d:10.1f} {b.median_d:10.1f} {b.max_d:10,d} {b.argmax_t:12,d}"
            f"   {b.mean_norm4:8.4f}                  {b.max_norm5:8.4f}                 {b.model_mean:10.1f}  {b.mean_ratio:7.3f}"
        )
    L.append("")
    L.append("  record gaps (t, d(t), d/((ln t)^5 lnln t)):")
    for t, d, r in res.records:
        L.append(f"    t = {t:12,d}   d = {d:9,d}   {r:.4f}")
    L.append("")
    L.append("  power-law thresholds ('Ingredient B' of the original note, d(t) <= t^theta):")
    L.append("    theta   twins with d(t) > t^theta   largest such t   (so d(t) <= t^theta for every twin beyond it, up to the limit)")
    for theta, n_exc, t_last in theta_exceedances(res):
        L.append(f"    {theta:.2f}    {n_exc:10,d}                {t_last:14,d}")
    return "\n".join(L)


def theta_exceedances(res: GapResult, thetas: Sequence[float] = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8)) -> list[tuple[float, int, int]]:
    """For each ``theta``: how many twins have ``d(t) > t^theta`` and the
    largest of them.  Since ``d(t)`` is conjecturally ``(log t)^{4+o(1)}``,
    every fixed ``theta > 0`` should have finitely many exceedances."""
    t = res.t.astype(float)
    d = res.d.astype(float)
    out = []
    for theta in thetas:
        exc = d > t**theta
        n_exc = int(exc.sum())
        t_last = int(res.t[exc].max()) if n_exc else 0
        out.append((theta, n_exc, t_last))
    return out
