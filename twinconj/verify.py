"""Independent verification of externally produced orbit files.

``verify_chain_csv`` re-checks a chain ``t -> 2t + d + 1`` written by the
generators of the *Twin-Gap Existence* note (``final.py`` /
``main.py``: columns ``step, t, d, C[, adjacency[, d_over_t]]``):

* primality of ``t, t+2, t+d, t+d+2, C, C+2`` and the side condition
  (``d-1`` or ``d+1`` prime) at every step;
* ``C = 2t + d + 1`` and ``C`` equals the next row's ``t``;
* optionally that ``d`` is the *least* productive gap of ``t`` (the
  generator is only a valid instance of ``d(t)`` if it scans ``d``
  upwards from 6);
* the normalised sizes ``d / ((log t)^4 log log t)`` (whose mean over all
  twins to 1e8 is 0.0575) and the Conjecture B' bound
  ``d <= (log t)^5 log log t``.

Numbers beyond the deterministic Miller-Rabin range (3.2e23) are tested
with gmpy2's BPSW + Miller-Rabin when available, otherwise with 12 fixed
Miller-Rabin bases; either way the result is "probable prime" for
integers of 20+ digits, as in the original generators.  For proofs run
``scripts/certify_chain.py`` (PARI/GP).
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass

from .chain import minimal_productive_gap as _minimal_slow
from .gaps import model_expected_min_gap, model_survival

try:
    from .fastgap import minimal_productive_gap_fast as _minimal_fast
except ImportError:  # pragma: no cover - gmpy2 missing
    _minimal_fast = None


def minimal_productive_gap(t: int, cap: int | None = None) -> int | None:
    """Least productive gap, sieve-accelerated when gmpy2 is available."""
    if _minimal_fast is not None and t > 10**6:
        return _minimal_fast(t, cap=cap)
    return _minimal_slow(t, cap=cap)
from .local import SingularSeries
from .primality import _DETERMINISTIC_LIMIT, is_lower_twin, is_prime

MEAN_NORM4_TO_1E8 = 0.0575


@dataclass
class ChainRow:
    step: int
    t: int
    d: int
    C: int
    ok_t: bool
    ok_td: bool
    ok_C: bool
    ok_side: bool
    ok_link: bool
    minimal: bool | None
    least_d: int | None
    model_mean: float | None = None
    survival: float | None = None

    @property
    def ok(self) -> bool:
        return self.ok_t and self.ok_td and self.ok_C and self.ok_side and self.ok_link \
            and (self.minimal is not False)

    @property
    def norm4(self) -> float:
        lt = math.log(self.t)
        return self.d / (lt**4 * math.log(max(lt, math.e)))

    @property
    def norm5(self) -> float:
        lt = math.log(self.t)
        return self.d / (lt**5 * math.log(max(lt, math.e)))


def read_chain(path: str) -> list[tuple[int, int, int, int]]:
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append((int(r["step"]), int(r["t"]), int(r["d"]), int(r["C"])))
    return rows


def verify_chain_csv(path: str, check_minimal: bool = True) -> list[ChainRow]:
    rows = read_chain(path)
    out: list[ChainRow] = []
    for i, (step, t, d, C) in enumerate(rows):
        ok_t = is_lower_twin(t)
        ok_td = is_lower_twin(t + d)
        ok_C = (C == 2 * t + d + 1) and is_lower_twin(C)
        ok_side = is_prime(d - 1) or is_prime(d + 1)
        ok_link = (i + 1 == len(rows)) or rows[i + 1][1] == C
        minimal = least = None
        if check_minimal and ok_t:
            least = minimal_productive_gap(t, cap=d)
            minimal = least == d
        out.append(ChainRow(step, t, d, C, ok_t, ok_td, ok_C, ok_side, ok_link, minimal, least))
    return out


def attach_model(rows: list[ChainRow], ss: SingularSeries | None = None) -> None:
    """Fill ``model_mean = E[d(t)]`` and ``survival = P(d(t) > d_observed)``
    from the Poisson model ``P(d(t) > Y) = exp(-E_t(Y))`` of ``twinconj.gaps``.
    Under the model the survival values of independent ``t`` are uniform on
    ``(0, 1)``; the steps of an orbit are not independent, but each ``t`` is
    a "fresh" twin as far as the local factors at small primes are
    concerned, so the same test is applied."""
    ss = ss or SingularSeries()
    for r in rows:
        if r.ok_t:
            r.model_mean = model_expected_min_gap(r.t, ss)
            r.survival = model_survival(r.t, ss, r.d)[1]


def ks_uniform(u: list[float]) -> float:
    """Kolmogorov-Smirnov distance between the empirical distribution of
    ``u`` and the uniform distribution on ``(0, 1)``."""
    n = len(u)
    if not n:
        return 0.0
    s = sorted(u)
    return max(max((i + 1) / n - x, x - i / n) for i, x in enumerate(s))


def format_chain_verification(path: str, rows: list[ChainRow]) -> str:
    L = [f"Verification of {path}: {len(rows)} steps"]
    L.append(f"  primality beyond {_DETERMINISTIC_LIMIT:.2e} is probabilistic (gmpy2 BPSW / 12-base Miller-Rabin)")
    L.append("")
    modelled = any(r.model_mean is not None for r in rows)
    head = "  step  digits(t)          d   side   d/((ln t)^4 lnln t)  d/((ln t)^5 lnln t)  checks        least d"
    if modelled:
        head += "     model E[d(t)]  P(d(t)>d)"
    L.append(head)
    for r in rows:
        side = ("d-1 " if is_prime(r.d - 1) else "") + ("d+1" if is_prime(r.d + 1) else "")
        checks = "OK" if r.ok else "FAIL:" + ",".join(
            n for n, v in (("t", r.ok_t), ("t+d", r.ok_td), ("C", r.ok_C), ("side", r.ok_side),
                           ("link", r.ok_link), ("minimal", r.minimal is not False)) if not v)
        least = "" if r.least_d is None else ("=" if r.minimal else f"{r.least_d}")
        line = f"  {r.step:4d}  {len(str(r.t)):9d}  {r.d:11,d}   {side:8s} {r.norm4:14.4f}      {r.norm5:14.5f}   {checks:12s} {least:8s}"
        if modelled:
            line += ("" if r.model_mean is None else f"  {r.model_mean:14,.0f}   {r.survival:8.4f}")
        L.append(line)
    bad = [r for r in rows if not r.ok]
    L.append("")
    L.append(f"  steps failing a check: {len(bad)}" + (f"  -> {[r.step for r in bad]}" if bad else ""))
    if rows:
        n4 = [r.norm4 for r in rows]
        big = [r for r in rows if r.t > 10**12]
        L.append(f"  mean d/((ln t)^4 lnln t) over all steps : {sum(n4) / len(n4):.4f}   (exhaustive mean to 1e8: {MEAN_NORM4_TO_1E8})")
        if big:
            n4b = [r.norm4 for r in big]
            L.append(f"  mean over the {len(big)} steps with t > 1e12 : {sum(n4b) / len(n4b):.4f}")
        L.append(f"  max d/((ln t)^5 lnln t) : {max(r.norm5 for r in rows):.5f}   (Conjecture B' asserts < 1 for every t >= 5)")
        L.append(f"  max d/t                 : {max(r.d / r.t for r in rows):.3e};  last t has {len(str(rows[-1].t))} digits")
        nonmin = [r for r in rows if r.minimal is False]
        if nonmin:
            L.append(f"  steps whose d is NOT the least productive gap: {len(nonmin)}  "
                     f"(the file is a valid orbit but not the orbit of d(t))")
    mod = [r for r in rows if r.model_mean is not None]
    if mod:
        u = [r.survival for r in mod]
        ratio = sum(r.d for r in mod) / sum(r.model_mean for r in mod)
        L.append("")
        L.append(f"  Poisson model P(d(t) > Y) = exp(-E_t(Y)) with Bateman-Horn E_t, over {len(mod)} steps:")
        L.append(f"    sum(observed d) / sum(model E[d(t)]) : {ratio:.4f}   (1 if the model is calibrated)")
        L.append(f"    mean of P(d(t) > d_observed)          : {sum(u) / len(u):.4f}   (0.5 under the model)")
        L.append(f"    KS distance of those values to U(0,1) : {ks_uniform(u):.4f}   "
                 f"(5% critical value ~ {1.358 / math.sqrt(len(u)):.4f})")
        big = [r for r in mod if r.t > 10**12]
        if big and len(big) < len(mod):
            ub = [r.survival for r in big]
            L.append(f"    same, restricted to the {len(big)} steps with t > 1e12: ratio "
                     f"{sum(r.d for r in big) / sum(r.model_mean for r in big):.4f}, mean survival "
                     f"{sum(ub) / len(ub):.4f}, KS {ks_uniform(ub):.4f}")
    return "\n".join(L)
