"""The constructive orbit ``t -> G(t) = 2t + d(t) + 1`` with exact minimal
productive gaps, for arbitrarily large integers (no numpy table; uses
:mod:`twinconj.primality`).

This replaces the interactive generator ``final.py`` of the original
repository: it is non-interactive, always takes the *minimal* productive gap,
and reports ``d(t)`` against the conjectured scale ``(log t)^4 log log t``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .primality import is_lower_twin, is_prime, next_lower_twin


@dataclass
class ChainStep:
    step: int
    t: int
    d: int
    G: int
    side: str

    @property
    def norm4(self) -> float:
        lt = math.log(self.t)
        return self.d / (lt**4 * math.log(max(lt, math.e)))


def minimal_productive_gap(t: int, cap: int | None = None) -> int | None:
    """Smallest productive gap of ``t`` (``t`` a lower twin, ``t >= 5``)."""
    if t == 5:
        return 6
    if t == 3:
        return None
    d = 6
    while cap is None or d <= cap:
        if (is_prime(d - 1) or is_prime(d + 1)) and is_lower_twin(t + d) and is_lower_twin(2 * t + d + 1):
            return d
        d += 6
    return None


def build_chain(start: int = 5, steps: int = 40, cap: int | None = None) -> list[ChainStep]:
    t = start if is_lower_twin(start) else next_lower_twin(start)
    if t == 3:
        t = 5
    out: list[ChainStep] = []
    for k in range(1, steps + 1):
        d = minimal_productive_gap(t, cap)
        if d is None:
            break
        m, p_ = is_prime(d - 1), is_prime(d + 1)
        side = "both" if (m and p_) else ("d-1" if m else "d+1")
        G = 2 * t + d + 1
        out.append(ChainStep(k, t, d, G, side))
        t = G
    return out


def format_chain(chain: list[ChainStep]) -> str:
    L = ["step  t                                d        G                                side     d/((ln t)^4 lnln t)"]
    for s in chain:
        L.append(f"{s.step:4d}  {s.t:<32d} {s.d:<8d} {s.G:<32d} {s.side:<8s} {s.norm4:8.4f}")
    if chain:
        last = chain[-1]
        L.append("")
        L.append(f"{len(chain)} steps; final term has {len(str(last.G))} digits; every G is a lower twin prime.")
    return "\n".join(L)
