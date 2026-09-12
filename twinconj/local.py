"""Local (residue-class) analysis of the linear-form tuples behind the
conjectures: admissibility, singular series, and the Bateman-Horn integral.

A linear form ``a*n + b`` is represented by the pair ``(a, b)``.

Tuples used in the package
--------------------------
``propagation_tuple(g)``
    ``(n, n+2, n+g, n+g+2, 2n+g+1, 2n+g+3)``: simultaneous primality means
    ``n`` and ``n+g`` are lower twins and their propagation candidate
    ``C = 2n+g+1`` is a lower twin.  The first four forms alone make up
    ``twin_pair_tuple(g)``.
``gap_tuple(t, sign)``
    forms in the variable ``d``: ``(d+t, d+t+2, d+2t+1, d+2t+3, d+sign)`` with
    ``sign = -1`` or ``+1``; simultaneous primality means ``d`` is a productive
    gap for ``t`` whose side condition is met by ``d-1`` resp. ``d+1``.
``gap_tuple_both(t)``
    the six forms with both ``d-1`` and ``d+1``.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Iterable, Sequence

import numpy as np

from .sieve import prime_table

Form = tuple[int, int]


# --------------------------------------------------------------------------
# tuples
# --------------------------------------------------------------------------

def twin_pair_tuple(g: int) -> tuple[Form, ...]:
    return ((1, 0), (1, 2), (1, g), (1, g + 2))


def propagation_tuple(g: int) -> tuple[Form, ...]:
    return twin_pair_tuple(g) + ((2, g + 1), (2, g + 3))


def gap_tuple(t: int, sign: int) -> tuple[Form, ...]:
    if sign not in (-1, 1):
        raise ValueError("sign must be -1 or +1")
    return ((1, t), (1, t + 2), (1, 2 * t + 1), (1, 2 * t + 3), (1, sign))


def gap_tuple_both(t: int) -> tuple[Form, ...]:
    return ((1, t), (1, t + 2), (1, 2 * t + 1), (1, 2 * t + 3), (1, -1), (1, 1))


# --------------------------------------------------------------------------
# residues
# --------------------------------------------------------------------------

def roots_mod(forms: Sequence[Form], q: int) -> set[int] | None:
    """Residues ``n mod q`` at which some form vanishes.

    Returns ``None`` when a form vanishes identically modulo ``q`` (then the
    tuple has the fixed divisor ``q``).
    """
    roots: set[int] = set()
    for a, b in forms:
        if a % q == 0:
            if b % q == 0:
                return None
            continue
        roots.add((-b * pow(a, -1, q)) % q)
    return roots


def nu(forms: Sequence[Form], q: int) -> int:
    r = roots_mod(forms, q)
    return q if r is None else len(r)


def surviving_residues(forms: Sequence[Form], q: int) -> list[int]:
    r = roots_mod(forms, q)
    if r is None:
        return []
    return [x for x in range(q) if x not in r]


def small_primes(limit: int) -> list[int]:
    return [int(p) for p in np.flatnonzero(prime_table(limit))]


def is_admissible(forms: Sequence[Form]) -> tuple[bool, int | None]:
    """Whether the product of the forms has no fixed prime divisor.

    Only primes ``q <= k`` (``k`` = number of forms) need to be enumerated: for
    ``q > k`` at most ``k < q`` residues are forbidden unless a form vanishes
    identically mod ``q``, which happens only when ``q`` divides
    ``gcd(a, b)``.  Returns ``(True, None)`` or ``(False, obstructing_prime)``.
    """
    k = len(forms)
    for a, b in forms:
        if a == 0:
            raise ValueError("forms must be non-constant")
        c = math.gcd(a, b)
        if c > 1:
            for q in small_primes(c):
                if c % q == 0:
                    return False, q
    for q in small_primes(max(k, 2)):
        if not surviving_residues(forms, q):
            return False, q
    return True, None


def special_primes(forms: Sequence[Form]) -> list[int]:
    """Primes at which ``nu`` can differ from the generic value ``k``.

    These are the primes ``q <= k``, the primes dividing a leading coefficient,
    and the primes dividing a non-zero cross difference ``a_j*b_i - a_i*b_j``
    (two roots coincide mod ``q`` exactly when ``q`` divides that number).
    """
    k = len(forms)
    special: set[int] = set(small_primes(max(k, 2)))
    numbers: set[int] = set()
    for a, _ in forms:
        numbers.add(abs(a))
    for i in range(k):
        for j in range(i + 1, k):
            ai, bi = forms[i]
            aj, bj = forms[j]
            numbers.add(abs(aj * bi - ai * bj))
    for m in numbers:
        special.update(_prime_factors(m))
    return sorted(special)


def special_primes_bounded(forms: Sequence[Form], primes: Iterable[int]) -> list[int]:
    """The primes among ``primes`` at which ``nu`` can differ from ``k``,
    found by divisibility of the product of the leading coefficients and
    cross differences.  Unlike :func:`special_primes` this never factors
    anything, so it works for forms with hundreds of digits; coincidences at
    primes outside ``primes`` are ignored (they change the singular series
    by a factor ``1 + O(1/q)``, negligible beyond the truncation point)."""
    k = len(forms)
    M = 1
    for a, _ in forms:
        M *= abs(a)
    for i in range(k):
        for j in range(i + 1, k):
            ai, bi = forms[i]
            aj, bj = forms[j]
            c = abs(aj * bi - ai * bj)
            if c:
                M *= c
    out = set(small_primes(max(k, 2)))
    for q in primes:
        q = int(q)
        if M % q == 0:
            out.add(q)
    return sorted(out)


@lru_cache(maxsize=None)
def _prime_factors(m: int) -> tuple[int, ...]:
    m = abs(m)
    out = []
    if m < 2:
        return ()
    for p in (2, 3, 5):
        if m % p == 0:
            out.append(p)
            while m % p == 0:
                m //= p
    f = 7
    step = (4, 2, 4, 2, 4, 6, 2, 6)
    i = 0
    while f * f <= m:
        if m % f == 0:
            out.append(f)
            while m % f == 0:
                m //= f
        f += step[i]
        i = (i + 1) % 8
    if m > 1:
        out.append(m)
    return tuple(out)


# --------------------------------------------------------------------------
# singular series
# --------------------------------------------------------------------------

def local_factor(forms: Sequence[Form], q: int) -> float:
    k = len(forms)
    return (1.0 - nu(forms, q) / q) * (1.0 - 1.0 / q) ** (-k)


def generic_log_factor(k: int, q: np.ndarray) -> np.ndarray:
    """``log[(1 - k/q)(1 - 1/q)^{-k}]`` for arrays of primes ``q > k``."""
    q = q.astype(float)
    return np.log1p(-k / q) - k * np.log1p(-1.0 / q)


class SingularSeries:
    """Evaluates ``S = prod_q (1 - nu_q/q)(1 - 1/q)^{-k}`` over primes
    ``q <= Q``, with the primes ``q > Q`` estimated by the analytic tail.

    For primes outside :func:`special_primes` every root is distinct, so the
    factor equals the generic ``(1 - k/q)(1 - 1/q)^{-k}``; those are summed
    once per ``k`` and re-used, which makes evaluating thousands of tuples
    cheap.
    """

    def __init__(self, Q: int = 1_000_000):
        self.Q = int(Q)
        self.primes = np.flatnonzero(prime_table(self.Q)).astype(np.int64)
        self._generic_total: dict[int, float] = {}

    def _generic(self, k: int) -> float:
        if k not in self._generic_total:
            q = self.primes[self.primes > k]
            self._generic_total[k] = float(np.sum(generic_log_factor(k, q)))
        return self._generic_total[k]

    def tail_log(self, k: int) -> float:
        """Estimate of ``sum_{q > Q} log[(1-k/q)(1-1/q)^{-k}]``.

        The summand is ``-(k^2 - k)/(2 q^2) + O(q^-3)`` and
        ``sum_{q > Q} q^-2 ~ 1/(Q log Q)``.
        """
        return -(k * k - k) / 2.0 / (self.Q * math.log(self.Q))

    def log_value(self, forms: Sequence[Form], with_tail: bool = True,
                  specials: Sequence[int] | None = None) -> float:
        """``log S``.  ``specials`` may supply the list of primes at which the
        root count is non-generic (see :func:`special_primes_bounded`);
        by default it is computed by factoring the cross differences."""
        k = len(forms)
        total = self._generic(k)
        for q in (special_primes(forms) if specials is None else specials):
            if q > self.Q:
                # A coincidence beyond the truncation point: fold the exact
                # factor in and treat the generic estimate as already counted
                # by the tail.
                total += math.log(local_factor(forms, q)) - float(
                    generic_log_factor(k, np.array([q]))[0]
                )
                continue
            f = local_factor(forms, q)
            if f <= 0.0:
                return -math.inf
            if q > k:
                total -= float(generic_log_factor(k, np.array([q]))[0])
            total += math.log(f)
        if with_tail:
            total += self.tail_log(k)
        return total

    def value(self, forms: Sequence[Form], with_tail: bool = True,
              specials: Sequence[int] | None = None) -> float:
        lv = self.log_value(forms, with_tail, specials)
        return 0.0 if lv == -math.inf else math.exp(lv)


# --------------------------------------------------------------------------
# quantities specific to the conjectures
# --------------------------------------------------------------------------

def propagation_ratio(g: int, ss: SingularSeries) -> float:
    """``R(g) = S_6(g) / S_4(g)``: the local correction to the probability
    that the propagation candidate of a twin pair with gap ``g`` is itself a
    lower twin.  For ``g = 0 (mod 6)`` the primes 2 and 3 contribute exactly
    ``4 * 9/4 = 9``.  Returns ``0.0`` when the gap is impossible for twins
    above 3 (``g != 0 mod 6``), where the model does not apply."""
    if g % 6 != 0:
        return 0.0
    return math.exp(
        ss.log_value(propagation_tuple(g)) - ss.log_value(twin_pair_tuple(g))
    )


def propagation_mean_ratio_model(Q: int = 3000) -> float:
    """Heuristic limiting value of the average of ``R(g_n)`` over consecutive
    twin pairs.

    Model: the consecutive gap ``g`` (a multiple of 6) falls in the class
    ``a (mod q)`` with probability proportional to the twin-pair local factor
    ``1 - nu_4(a, q)/q``, independently for different ``q`` (this is the usual
    Hardy-Littlewood gap heuristic, and it reproduces the bias of prime gaps
    towards multiples of small primes).  Then

        E[R] = 9 * prod_{q >= 5} [sum_a (1 - nu_6(a,q)/q)] / [sum_a (1 - nu_4(a,q)/q)] * (1 - 1/q)^{-2}.

    The factors are ``1 + O(q^-2)``, so ``Q = 3000`` already gives four digits.
    """
    log_e = math.log(9.0)
    for q in small_primes(Q):
        if q < 5:
            continue
        num = sum(1.0 - nu(propagation_tuple(a), q) / q for a in range(q))
        den = sum(1.0 - nu(twin_pair_tuple(a), q) / q for a in range(q))
        log_e += math.log(num / den) - 2.0 * math.log1p(-1.0 / q)
    return math.exp(log_e)


def gap_series(t: int, ss: SingularSeries) -> tuple[float, float, float]:
    """Singular series of the two 5-tuples and the 6-tuple at ``t``:
    ``(S_minus, S_plus, S_both)``.  For ``t`` beyond 60 bits the special
    primes are located by divisibility instead of factorisation."""
    forms = (gap_tuple(t, -1), gap_tuple(t, +1), gap_tuple_both(t))
    if t.bit_length() > 60:
        return tuple(ss.value(f, specials=special_primes_bounded(f, ss.primes)) for f in forms)  # type: ignore[return-value]
    return tuple(ss.value(f) for f in forms)  # type: ignore[return-value]


def gap_series_lower_bound(Q: int = 1_000_000) -> dict[str, float]:
    """Rigorous positive lower bound, uniform over all ``t in T`` with
    ``t > 5``, for the singular series of ``gap_tuple(t, -1)``.

    Proof sketch (machine-checked in :mod:`twinconj.certificate`):

    * ``q = 2``: all five forms are odd when ``d`` is even, ``nu_2 = 1``.
    * ``q = 3``: ``nu_3 = 2`` (only ``d = 0 (mod 3)`` survives) for every
      ``t = 2 (mod 3)``.
    * ``q = 5``: ``nu_5 <= 4`` for ``t = 1, 2, 4 (mod 5)`` (the classes a
      lower twin ``t > 5`` can occupy).
    * ``q >= 7``: ``nu_q <= 5 < q``.

    Every factor is therefore at least ``(1 - 5/q)(1 - 1/q)^{-5}`` for
    ``q >= 7``.  Since ``log[(1-5/q)(1-1/q)^{-5}] >= -25/q^2`` for ``q >= 10``
    and ``sum_{q > Q} q^{-2} < 1/Q``, the tail product is at least
    ``exp(-25/Q)``.
    """
    primes = np.flatnonzero(prime_table(Q)).astype(np.int64)
    q = primes[primes >= 7]
    log_mid = float(np.sum(generic_log_factor(5, q)))
    f2 = (1 - 1 / 2) * (1 - 1 / 2) ** (-5)
    f3 = (1 - 2 / 3) * (1 - 1 / 3) ** (-5)
    f5 = (1 - 4 / 5) * (1 - 1 / 5) ** (-5)
    tail = math.exp(-25.0 / Q)
    lower = f2 * f3 * f5 * math.exp(log_mid) * tail
    return {
        "Q": Q,
        "factor_2": f2,
        "factor_3": f3,
        "factor_5_worst": f5,
        "product_7_to_Q": math.exp(log_mid),
        "tail_lower_bound": tail,
        "S_min": lower,
    }


def bateman_horn_integral(forms: Sequence[Form], X: float, lo: float = 2.0,
                          points: int = 20_000) -> float:
    """``int_lo^X dt / prod_i log f_i(t)`` on a log-spaced grid."""
    if X <= lo:
        return 0.0
    t = np.geomspace(lo, X, points)
    denom = np.ones_like(t)
    for a, b in forms:
        v = a * t + b
        v = np.where(v > 2.0, v, 2.0)
        denom *= np.log(v)
    return float(np.trapezoid(1.0 / denom, t))


TWIN_PRIME_CONSTANT = 0.6601618158468695739278121100145557784326233602847334133194484233354056423


def twin_prime_constant_numeric(Q: int = 1_000_000) -> float:
    """``C_2 = prod_{q >= 3} q(q-2)/(q-1)^2`` truncated at ``Q`` (sanity check
    for the singular-series machinery)."""
    primes = np.flatnonzero(prime_table(Q)).astype(float)
    q = primes[primes >= 3]
    return float(np.exp(np.sum(np.log(q * (q - 2) / (q - 1) ** 2))))
