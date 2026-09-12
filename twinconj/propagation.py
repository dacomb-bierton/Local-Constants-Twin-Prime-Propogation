"""Quantitative form of the Twin-Prime Propagation Conjecture.

For consecutive lower twins ``p < q`` with gap ``g = q - p`` the candidate is
``C = p + q + 1``.  The refined conjecture (Conjecture A' in
``REFINED_CONJECTURES.md``) says the number of propagating pairs with
``p <= X`` is asymptotic to

    sum_{p_n <= X}  R(g_n) / ( log C_n * log (C_n + 2) ),

where ``R(g) = S_6(g) / S_4(g)`` is the ratio of the singular series of the
six-form tuple ``(n, n+2, n+g, n+g+2, 2n+g+1, 2n+g+3)`` and of the four-form
tuple ``(n, n+2, n+g, n+g+2)``.  This module measures both sides.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .local import (
    TWIN_PRIME_CONSTANT,
    SingularSeries,
    bateman_horn_integral,
    propagation_ratio,
    propagation_tuple,
    twin_pair_tuple,
)
from .sieve import lower_twins, prime_table


@dataclass
class DyadicRow:
    lo: int
    hi: int
    pairs: int
    success: int
    predicted: float
    mean_R: float

    @property
    def rate(self) -> float:
        return self.success / self.pairs if self.pairs else float("nan")

    @property
    def predicted_rate(self) -> float:
        return self.predicted / self.pairs if self.pairs else float("nan")

    @property
    def ratio(self) -> float:
        return self.success / self.predicted if self.predicted else float("nan")


@dataclass
class GapRow:
    g: int
    pairs: int
    success: int
    predicted: float
    R: float

    @property
    def ratio(self) -> float:
        return self.success / self.predicted if self.predicted else float("nan")


@dataclass
class PropagationResult:
    limit: int
    n_twins: int
    n_pairs: int
    n_success: int
    predicted: float
    d_branch_pairs: list[tuple[int, int]]
    dyadic: list[DyadicRow] = field(default_factory=list)
    by_gap: list[GapRow] = field(default_factory=list)
    gap6_pairs: int = 0
    gap6_pairs_hl: float = 0.0
    gap6_success: int = 0
    gap6_success_bh: float = 0.0
    S4_6: float = 0.0
    S6_6: float = 0.0
    first_successes: list[tuple[int, int, int]] = field(default_factory=list)
    mean_R: float = 0.0
    kappa: float = 0.0
    kappa_prediction: float = 0.0  # kappa * int_5^X dt / ((log t)^2 (log 2t)^2)

    @property
    def ratio(self) -> float:
        return self.n_success / self.predicted if self.predicted else float("nan")


def run_propagation(limit: int, ss: SingularSeries | None = None,
                    max_gap_rows: int = 120) -> PropagationResult:
    limit = int(limit)
    ss = ss or SingularSeries()

    # C = p + q + 1 <= 2*limit + (gap) + 1; the next lower twin after ``limit``
    # is what q can be, so give the table some slack and clip.
    slack = 4_000
    table_limit = 2 * limit + slack
    is_p = prime_table(table_limit)
    twins = lower_twins(is_p, limit + slack // 2)
    twins = twins[: np.searchsorted(twins, limit, side="right") + 1]
    if len(twins) < 2:
        raise ValueError("limit too small")

    p = twins[:-1]
    q = twins[1:]
    keep = p <= limit
    p, q = p[keep], q[keep]
    g = q - p
    C = p + q + 1
    valid = C + 4 <= table_limit
    p, q, g, C = p[valid], q[valid], g[valid], C[valid]

    c_twin = is_p[C] & is_p[C + 2]
    d_twin = is_p[C + 2] & is_p[C + 4]
    success = c_twin | d_twin

    uniq_g, inv = np.unique(g, return_inverse=True)
    R_uniq = np.array([propagation_ratio(int(gg), ss) for gg in uniq_g])
    R = R_uniq[inv]
    logs = np.log(C.astype(float)) * np.log(C.astype(float) + 2.0)
    prob = R / logs

    result = PropagationResult(
        limit=limit,
        n_twins=int(np.count_nonzero(twins <= limit)),
        n_pairs=int(len(p)),
        n_success=int(np.count_nonzero(success)),
        predicted=float(prob.sum()),
        d_branch_pairs=[(int(a), int(b)) for a, b in zip(p[d_twin], q[d_twin])],
    )

    idx = np.flatnonzero(success)[:10]
    result.first_successes = [(int(p[i]), int(q[i]), int(C[i])) for i in idx]

    # closed-form version: N(X) ~ kappa * int dt / ((log t)^2 (log 2t)^2),
    # kappa = 2 C_2 * E[R(g)], with E[R] taken over the pairs with p > 3.
    result.mean_R = float(R[p > 3].mean())
    result.kappa = 2 * TWIN_PRIME_CONSTANT * result.mean_R
    result.kappa_prediction = result.kappa * bateman_horn_integral(((1, 0), (1, 0), (2, 0), (2, 0)), limit, lo=5.0)

    # dyadic blocks by p
    k = np.floor(np.log2(np.maximum(p, 1))).astype(int)
    for kk in range(int(k.min()), int(k.max()) + 1):
        m = k == kk
        if not m.any():
            continue
        result.dyadic.append(
            DyadicRow(
                lo=1 << kk,
                hi=1 << (kk + 1),
                pairs=int(m.sum()),
                success=int(success[m].sum()),
                predicted=float(prob[m].sum()),
                mean_R=float(R[m].mean()),
            )
        )

    # gap-resolved
    for gg, RR in zip(uniq_g, R_uniq):
        if gg > max_gap_rows:
            break
        m = g == gg
        result.by_gap.append(
            GapRow(
                g=int(gg),
                pairs=int(m.sum()),
                success=int(success[m].sum()),
                predicted=float(prob[m].sum()),
                R=float(RR),
            )
        )

    # gap 6: exact Bateman-Horn comparison (consecutiveness is automatic)
    m6 = g == 6
    result.gap6_pairs = int(m6.sum())
    result.gap6_success = int(success[m6].sum())
    result.S4_6 = ss.value(twin_pair_tuple(6))
    result.S6_6 = ss.value(propagation_tuple(6))
    result.gap6_pairs_hl = result.S4_6 * bateman_horn_integral(twin_pair_tuple(6), limit)
    result.gap6_success_bh = result.S6_6 * bateman_horn_integral(propagation_tuple(6), limit)
    return result


def format_report(res: PropagationResult) -> str:
    lines = []
    lines.append(f"Twin-Prime Propagation, p_n <= {res.limit:,}")
    lines.append(f"  lower twins            : {res.n_twins:,}")
    lines.append(f"  consecutive pairs      : {res.n_pairs:,}")
    lines.append(f"  propagating pairs      : {res.n_success:,}")
    lines.append(f"  predicted (Conj. A')   : {res.predicted:,.1f}")
    lines.append(f"  actual / predicted     : {res.ratio:.4f}")
    lines.append(f"  mean R(g) over pairs   : {res.mean_R:.4f}   kappa = 2*C_2*mean R = {res.kappa:.4f}")
    lines.append(f"  kappa * int_5^X dt/((ln t)^2 (ln 2t)^2) : {res.kappa_prediction:,.1f}   actual/that = {res.n_success / res.kappa_prediction:.4f}")
    lines.append(f"  D-branch successes     : {res.d_branch_pairs}  (Lemma: only (3,5))")
    lines.append(f"  first successes (p,q,C): {res.first_successes[:6]}")
    lines.append("")
    lines.append("  dyadic block [lo, hi)      pairs   success  predicted   ratio   rate      pred.rate  mean R")
    for r in res.dyadic:
        lines.append(
            f"  [2^{int(math.log2(r.lo)):2d}, 2^{int(math.log2(r.hi)):2d})   {r.pairs:10,d} {r.success:9,d} {r.predicted:11.1f} "
            f"{r.ratio:7.3f}  {r.rate:.6f}  {r.predicted_rate:.6f}  {r.mean_R:6.3f}"
        )
    lines.append("")
    lines.append("  gap g    pairs     success  predicted  ratio    R(g)")
    for r in res.by_gap:
        lines.append(f"  {r.g:5d} {r.pairs:9,d} {r.success:9,d} {r.predicted:10.1f} {r.ratio:7.3f}  {r.R:7.3f}")
    lines.append("")
    lines.append("  Gap-6 pairs are prime quadruplets (n, n+2, n+6, n+8):")
    lines.append(f"    consecutive gap-6 pairs   : {res.gap6_pairs:,}   Hardy-Littlewood: {res.gap6_pairs_hl:,.1f}   (S_4(6) = {res.S4_6:.5f})")
    lines.append(f"    propagating gap-6 pairs   : {res.gap6_success:,}   Bateman-Horn    : {res.gap6_success_bh:,.1f}   (S_6(6) = {res.S6_6:.5f})")
    return "\n".join(lines)
