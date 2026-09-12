"""Generic prime-constellation experiment: for any admissible tuple of
linear forms ``a_i n + b_i`` count the ``n <= X`` at which all forms are
prime and compare with

* the Bateman-Horn prediction ``S * int_2^X dt / prod_i log(a_i t + b_i)``
  (a conjecture), and
* the leading term of the Selberg-sieve upper bound
  ``2^k k! * S * X / (log X)^k`` (Halberstam-Richert, *Sieve Methods*,
  Theorem 5.7 - unconditional, valid for every admissible tuple of distinct
  linear forms).

The same machinery that produced Conjectures A' and B' therefore yields a
tested quantitative conjecture *and* the best unconditional statement for
any related constellation.  Presets cover the natural relatives of the
propagation and gap conjectures.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .local import Form, SingularSeries, bateman_horn_integral, is_admissible
from .sieve import prime_table

PRESETS: dict[str, tuple[str, str]] = {
    "twin": ("n, n+2", "twin primes"),
    "cousin": ("n, n+4", "cousin primes"),
    "sexy": ("n, n+6", "sexy primes"),
    "sophie-germain": ("n, 2n+1", "Sophie Germain primes"),
    "cunningham-3": ("n, 2n+1, 4n+3", "Cunningham chains of length 3"),
    "bi-twin": ("n, n+2, 2n+1, 2n+3", "bi-twin chain of one link (OEIS A066388 shifted by 1): twin centre doubled is a twin centre"),
    "twin-germain": ("n, n+2, 2n+1", "twin pair whose lower member is Sophie Germain"),
    "quadruplet": ("n, n+2, n+6, n+8", "prime quadruplets = consecutive lower twins at gap 6"),
    "propagation-6": ("n, n+2, n+6, n+8, 2n+7, 2n+9", "propagating consecutive twin pair at gap 6 (Theorem A)"),
    "propagation-12": ("n, n+2, n+12, n+14, 2n+13, 2n+15", "twin pairs at gap 12 whose C is a lower twin"),
}

_FORM_RE = re.compile(r"^\s*(?:(-?\d*)\s*\*?\s*n)?\s*([+-]\s*\d+)?\s*$")


def parse_forms(spec: str) -> tuple[Form, ...]:
    """``"n, n+2, 2n+7"`` -> ``((1,0), (1,2), (2,7))``."""
    forms: list[Form] = []
    for piece in spec.split(","):
        piece = piece.strip()
        if not piece:
            continue
        m = _FORM_RE.match(piece.replace(" ", ""))
        if not m or (m.group(1) is None and m.group(2) is None):
            raise ValueError(f"cannot parse linear form {piece!r}")
        a_str, b_str = m.group(1), m.group(2)
        if a_str is None:
            a = 0
        elif a_str in ("", "+"):
            a = 1
        elif a_str == "-":
            a = -1
        else:
            a = int(a_str)
        b = int(b_str.replace(" ", "")) if b_str else 0
        if a <= 0:
            raise ValueError(f"leading coefficient must be positive in {piece!r}")
        forms.append((a, b))
    if len(set(forms)) != len(forms):
        raise ValueError("forms must be distinct")
    return tuple(forms)


def forms_to_str(forms: Sequence[Form]) -> str:
    out = []
    for a, b in forms:
        s = "n" if a == 1 else f"{a}n"
        if b > 0:
            s += f"+{b}"
        elif b < 0:
            s += f"{b}"
        out.append(s)
    return ", ".join(out)


@dataclass
class ConstellationBlock:
    lo: int
    hi: int
    count: int
    predicted: float

    @property
    def ratio(self) -> float:
        return self.count / self.predicted if self.predicted else float("nan")


@dataclass
class ConstellationResult:
    forms: tuple[Form, ...]
    limit: int
    count: int
    S: float
    predicted: float
    sieve_upper_bound: float
    first: list[int] = field(default_factory=list)
    blocks: list[ConstellationBlock] = field(default_factory=list)

    @property
    def k(self) -> int:
        return len(self.forms)

    @property
    def ratio(self) -> float:
        return self.count / self.predicted if self.predicted else float("nan")


def run_constellation(forms: Sequence[Form], limit: int, ss: SingularSeries | None = None,
                      chunk: int = 10_000_000) -> ConstellationResult:
    forms = tuple(forms)
    limit = int(limit)
    ok, q = is_admissible(forms)
    if not ok:
        raise ValueError(f"tuple {forms_to_str(forms)} is not admissible: fixed divisor {q}")
    ss = ss or SingularSeries()
    S = ss.value(forms)

    n_min = max(1, max(-(b // a) + 1 for a, b in forms))  # all forms >= 2 roughly
    table_limit = max(a * limit + b for a, b in forms) + 2
    is_p = prime_table(table_limit)

    total = 0
    first: list[int] = []
    block_counts: dict[int, int] = {}
    for lo in range(n_min, limit + 1, chunk):
        hi = min(lo + chunk, limit + 1)
        n = np.arange(lo, hi, dtype=np.int64)
        mask = np.ones(len(n), dtype=bool)
        for a, b in forms:
            v = a * n + b
            mask &= (v >= 2) & is_p[np.maximum(v, 0)]
        hits = n[mask]
        total += int(len(hits))
        if len(first) < 10:
            first.extend(int(x) for x in hits[: 10 - len(first)])
        if len(hits):
            k = np.floor(np.log2(hits)).astype(int)
            for kk, c in zip(*np.unique(k, return_counts=True)):
                block_counts[int(kk)] = block_counts.get(int(kk), 0) + int(c)

    k = len(forms)
    res = ConstellationResult(
        forms=forms,
        limit=limit,
        count=total,
        S=S,
        predicted=S * bateman_horn_integral(forms, limit),
        sieve_upper_bound=(2**k) * math.factorial(k) * S * limit / math.log(limit) ** k,
        first=first,
    )
    for kk in range(0, int(math.log2(limit)) + 1):
        lo, hi = 1 << kk, min(1 << (kk + 1), limit + 1)
        if hi <= lo:
            continue
        pred = S * (bateman_horn_integral(forms, hi) - bateman_horn_integral(forms, lo))
        res.blocks.append(ConstellationBlock(lo, hi, block_counts.get(kk, 0), pred))
    return res


def format_report(res: ConstellationResult, description: str | None = None) -> str:
    L = []
    L.append(f"Constellation ({forms_to_str(res.forms)})" + (f" - {description}" if description else ""))
    L.append(f"  n <= {res.limit:,}, k = {res.k} forms, singular series S = {res.S:.6f}")
    L.append(f"  count                        : {res.count:,}")
    L.append(f"  Bateman-Horn prediction      : {res.predicted:,.1f}   (actual/predicted = {res.ratio:.4f})")
    L.append(f"  Selberg upper bound, leading : {res.sieve_upper_bound:,.0f}   (= 2^k k! S X/(log X)^k; unconditional)")
    L.append(f"  first n                      : {res.first}")
    L.append("")
    L.append("  block [lo,hi)        count     predicted    ratio")
    for b in res.blocks:
        if b.count == 0 and b.predicted < 0.5:
            continue
        L.append(f"  [2^{int(math.log2(b.lo)):2d},2^{int(math.log2(b.lo)) + 1:2d})  {b.count:10,d}  {b.predicted:12.1f}  {b.ratio:7.3f}")
    return "\n".join(L)
