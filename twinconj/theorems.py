"""Closed forms and identities for the local constants of the propagation
conjecture.  Everything here is unconditional: statements about Euler
products and residue counts, not about primes.  The proofs are in
``paper/bierton_local_constants.tex``; the certificate in
:mod:`twinconj.certificate` re-checks every finite step by enumeration and
every constant by independent numerical evaluation.

Notation.  For a gap ``g = 0 (mod 6)`` let ``S_4(g)`` be the singular series
of ``(n, n+2, n+g, n+g+2)`` and ``S_6(g)`` that of the propagation 6-tuple
``(n, n+2, n+g, n+g+2, 2n+g+1, 2n+g+3)``.  ``R(g) = S_6(g)/S_4(g)`` is the
local correction to the probability that a twin pair with gap ``g`` has a
lower-twin propagation candidate.  ``Delta(g) = g (g^2-1)(g^2-4)(g^2-9)``.

Theorem 1 (explicit local ratio).  For every prime ``q >= 5``

    nu_4(g; q) = 2 if q | g,  3 if q | g^2-4,  4 otherwise;
    nu_6(g; q) = nu_4(g; q) if q | (g^2-1)(g^2-9),  nu_4(g; q) + 2 otherwise;

so that, with ``rho_q(g) = q^2 (q - nu_6) / ((q-1)^2 (q - nu_4))`` and the
generic value ``gamma_q = q^2 (q-6) / ((q-1)^2 (q-4))`` (only attained for
``q >= 11``),

    R(g) = R_inf * rho_5(g) * rho_7(g) * prod_{q >= 11, q | Delta(g)} rho_q(g)/gamma_q,
    R_inf = 9 * prod_{q >= 11} gamma_q = 5.87825...

Corollary.  ``R_min := R_inf * (25/48) * (49/72) = 2.0838... < R(g) <<
(log log g)^2`` for every ``g``, and ``R_min`` is the infimum.

Theorem 2 (mean values over gaps).  As ``G -> oo``,

    (6/G) sum_{g <= G, 6|g} S_4(g) -> 24 C_2^2 = (27/2) prod_{q>=5} q^2 (q-2)^2 / (q-1)^4,
    (6/G) sum_{g <= G, 6|g} S_6(g) -> 24 C_2^2 * Rbar,
    Rbar = 9 prod_{q>=5} q^2 (q^2 - 6q + 12) / ((q-1)^2 (q-2)^2) = 11.1849...,

and hence ``kappa = 2 C_2 Rbar = (27/2) prod_{q>=5} q^3 (q^2-6q+12) /
((q-1)^4 (q-2)) = 14.7677...`` is the constant of Conjecture A'.

Theorem 3 (identities).  ``S(n, n+2, 2n+1, 2n+3) = S(n, n+2, n+6, n+8)``
(bi-twin chains are locally as likely as prime quadruplets) and
``S_6(6) = 3 S(n, n+4, n+6, n+10, n+12, n+16)`` (a propagating gap-6 pair is
locally exactly three times as likely as a prime sextuplet).
"""

from __future__ import annotations

import math
from typing import Callable, Sequence

import numpy as np

from .local import (
    Form,
    SingularSeries,
    TWIN_PRIME_CONSTANT,
    nu,
    propagation_tuple,
    small_primes,
    twin_pair_tuple,
)
from .sieve import prime_table

# --------------------------------------------------------------------------
# Theorem 1: explicit residue counts and the local ratio
# --------------------------------------------------------------------------


def delta(g: int) -> int:
    """``Delta(g) = g (g^2-1)(g^2-4)(g^2-9)``: a prime ``q >= 5`` changes the
    generic root counts of the gap tuples exactly when it divides this."""
    return g * (g * g - 1) * (g * g - 4) * (g * g - 9)


def nu4_gap(g: int, q: int) -> int:
    """Roots mod ``q >= 5`` of ``n (n+2)(n+g)(n+g+2)``: the roots are
    ``0, -2, -g, -g-2`` and coincidences happen only for ``q | g`` (two
    coincidences) or ``q | g +- 2`` (one)."""
    if g % q == 0:
        return 2
    if (g * g - 4) % q == 0:
        return 3
    return 4


def nu6_gap(g: int, q: int) -> int:
    """Roots mod ``q >= 5`` of the propagation 6-tuple.  The two extra roots
    ``-(g+1)/2`` and ``-(g+3)/2`` coincide with roots of the 4-tuple exactly
    when ``q`` divides one of ``g-3, g-1, g+1, g+3``; in that case *both*
    coincide, and ``q`` divides at most one of the four for ``q >= 5``."""
    n4 = nu4_gap(g, q)
    if ((g * g - 1) * (g * g - 9)) % q == 0:
        return n4
    return n4 + 2


def rho(g: int, q: int) -> float:
    """Local factor of ``R(g)`` at the prime ``q >= 5``."""
    n4, n6 = nu4_gap(g, q), nu6_gap(g, q)
    return q * q * (q - n6) / ((q - 1) ** 2 * (q - n4))


def gamma(q: float) -> float:
    """Generic local factor ``q^2 (q-6) / ((q-1)^2 (q-4))`` (``q >= 11``)."""
    return q * q * (q - 6) / ((q - 1) ** 2 * (q - 4))


def _euler_product(log_factor: Callable[[np.ndarray], np.ndarray], Q: int,
                   q_min: int, tail_coefficient: float, tail: bool = True) -> float:
    """``exp(sum_{q_min <= q <= Q} log_factor(q))`` with the tail
    ``sum_{q > Q} log_factor(q) ~ -c / (Q log Q)`` added, where the factor is
    ``1 - c/q^2 + O(q^-3)``.  ``tail=False`` returns the bare finite product."""
    primes = np.flatnonzero(prime_table(Q)).astype(float)
    q = primes[primes >= q_min]
    total = float(np.sum(log_factor(q)))
    if tail:
        # sum_{q > Q} q^-2 = int_Q^oo dt / (t^2 log t) (1 + o(1)) = (1 - 1/log Q + O(1/log^2 Q)) / (Q log Q)
        lq = math.log(Q)
        total -= tail_coefficient / (Q * lq) * (1.0 - 1.0 / lq)
    return math.exp(total)


def r_infinity(Q: int = 10_000_000, tail: bool = True) -> float:
    """``R_inf = 9 prod_{q >= 11} gamma_q`` (``gamma_q = 1 - 9/q^2 + ...``)."""
    return 9.0 * _euler_product(lambda q: np.log(gamma(q)), Q, 11, 9.0, tail)


def propagation_ratio_explicit(g: int, r_inf: float | None = None) -> float:
    """``R(g)`` from Theorem 1: a finite product over the primes dividing
    ``Delta(g)`` times the universal constant ``R_inf``.  Only the prime
    factors of ``Delta(g)`` are needed, no sieve and no truncation."""
    if g % 6 != 0 or g <= 0:
        raise ValueError("g must be a positive multiple of 6")
    if r_inf is None:
        r_inf = r_infinity()
    value = r_inf * rho(g, 5) * rho(g, 7)
    for q in _prime_factors_ge(delta(g), 11):
        value *= rho(g, q) / gamma(q)
    return value


def _prime_factors_ge(m: int, lo: int) -> list[int]:
    m = abs(m)
    out = []
    for p in (2, 3, 5, 7):
        while m % p == 0:
            m //= p
    f = 11
    while f * f <= m:
        if m % f == 0:
            out.append(f)
            while m % f == 0:
                m //= f
        f += 2
    if m > 1:
        out.append(m)
    return [p for p in out if p >= lo]


def propagation_ratio_bounds(r_inf: float | None = None) -> dict[str, float]:
    """Sharp lower bound ``R_min`` for ``R(g)`` over all ``g = 0 (mod 6)``.

    For ``q >= 11`` the generic factor ``gamma_q`` is the smallest of the
    four possible values of ``rho_q``, so the infimum is attained by the
    residue classes minimising ``rho_5`` (``g = 0 mod 5``: 25/48) and
    ``rho_7`` (``g = +-2 mod 7``: 49/72), with no prime ``q >= 11`` dividing
    ``Delta(g)``.  By Sylvester--Schur the seven consecutive integers
    ``g-3, ..., g+3`` have a prime factor ``> 7`` whenever ``g >= 11``, so
    the infimum is approached but attained by no ``g >= 12``."""
    if r_inf is None:
        r_inf = r_infinity()
    rho5 = {a: rho(a, 5) for a in range(5)}
    rho7 = {a: rho(a, 7) for a in range(7)}
    return {
        "R_inf": r_inf,
        "rho_5_min": min(rho5.values()),
        "rho_7_min": min(rho7.values()),
        "R_min": r_inf * min(rho5.values()) * min(rho7.values()),
        "rho_5_max": max(rho5.values()),
        "rho_7_max": max(rho7.values()),
        "R_generic_max": r_inf * max(rho5.values()) * max(rho7.values()),
    }


# --------------------------------------------------------------------------
# Theorem 2: mean values over gaps, Rbar and kappa
# --------------------------------------------------------------------------


def mean_twin_pair_series(Q: int = 10_000_000) -> float:
    """``lim (6/G) sum_{g <= G, 6 | g} S_4(g) = (27/2) prod_{q>=5} q^2 (q-2)^2/(q-1)^4``."""
    return 13.5 * _euler_product(
        lambda q: 2 * np.log(q) + 2 * np.log(q - 2) - 4 * np.log(q - 1), Q, 5, 2.0)


def mean_propagation_series(Q: int = 10_000_000) -> float:
    """``lim (6/G) sum_{g <= G, 6 | g} S_6(g) = (243/2) prod_{q>=5} q^4 (q^2-6q+12)/(q-1)^6``."""
    return 121.5 * _euler_product(
        lambda q: 4 * np.log(q) + np.log(q * q - 6 * q + 12) - 6 * np.log(q - 1), Q, 5, 3.0)


def mean_ratio_closed_form(Q: int = 10_000_000) -> float:
    """``Rbar = 9 prod_{q>=5} q^2 (q^2-6q+12) / ((q-1)^2 (q-2)^2)``: the
    ``S_4``-weighted mean of ``R(g)`` over gaps, i.e. the limiting mean of
    ``R(g_n)`` over consecutive twin pairs in the Hardy--Littlewood model."""
    return 9.0 * _euler_product(
        lambda q: 2 * np.log(q) + np.log(q * q - 6 * q + 12) - 2 * np.log(q - 1) - 2 * np.log(q - 2),
        Q, 5, 1.0)


def kappa_closed_form(Q: int = 10_000_000) -> float:
    """``kappa = 2 C_2 Rbar = (27/2) prod_{q>=5} q^3 (q^2-6q+12) / ((q-1)^4 (q-2))``."""
    return 13.5 * _euler_product(
        lambda q: 3 * np.log(q) + np.log(q * q - 6 * q + 12) - 4 * np.log(q - 1) - np.log(q - 2),
        Q, 5, 2.0)


def mean_local_factor(k: int, q: int) -> float:
    """Average over ``g mod q`` of ``(1 - nu_k(g; q)/q)(1 - 1/q)^{-k}`` for
    ``k = 4`` (twin-pair tuple) or ``k = 6`` (propagation tuple), computed by
    enumeration; equals ``(q-2)^2/q^2`` resp. ``(q^2-6q+12)/q^2`` times
    ``(1-1/q)^{-k}`` by Theorem 2."""
    make = twin_pair_tuple if k == 4 else propagation_tuple
    return sum(1.0 - nu(make(a), q) / q for a in range(q)) / q * (1.0 - 1.0 / q) ** (-k)


def finite_height_mean_ratio(x: float, ss: SingularSeries, gmax: int | None = None) -> tuple[float, float]:
    """Hardy--Littlewood prediction for the mean of ``R(g_n)`` over consecutive
    twin pairs near height ``x``: gaps are weighted by ``S_4(g) exp(-lambda g)``
    with ``lambda = 2 C_2 / (log x)^2`` the twin density.  Returns
    ``(mean R, mean gap)``.  Converges to ``Rbar`` as ``x -> oo``; at
    ``x = 10^9`` it is about 11.34, which is what the data show.  The sum is
    cut at ``gmax`` (default ``20/lambda``, where the weight is ``e^-20``)."""
    lam = 2 * TWIN_PRIME_CONSTANT / math.log(x) ** 2
    if gmax is None:
        gmax = 6 * int(20 / lam / 6) + 6
    num = den = gsum = 0.0
    for g in range(6, gmax + 1, 6):
        w = ss.value(twin_pair_tuple(g)) * math.exp(-lam * g)
        num += w * ss.value(propagation_tuple(g)) / ss.value(twin_pair_tuple(g))
        den += w
        gsum += w * g
    return num / den, gsum / den


# --------------------------------------------------------------------------
# Theorem 3: singular-series identities
# --------------------------------------------------------------------------

BI_TWIN: tuple[Form, ...] = ((1, 0), (1, 2), (2, 1), (2, 3))
QUADRUPLET: tuple[Form, ...] = ((1, 0), (1, 2), (1, 6), (1, 8))
SEXTUPLET: tuple[Form, ...] = ((1, 0), (1, 4), (1, 6), (1, 10), (1, 12), (1, 16))
PROPAGATION_6: tuple[Form, ...] = propagation_tuple(6)


def root_count_profile(forms: Sequence[Form], Q: int) -> dict[int, int]:
    """``{q: nu(q)}`` for all primes ``q <= Q``."""
    return {q: nu(forms, q) for q in small_primes(Q)}


def identity_bi_twin_quadruplet(Q: int = 1000) -> tuple[bool, dict[int, tuple[int, int]]]:
    """``nu`` agrees at every prime for the bi-twin and quadruplet tuples.
    For ``q >= 5`` both have four distinct roots (the pairwise root
    differences of the bi-twin tuple are ``2, 1/2, 3/2, 3/2, 1/2, 1`` and of
    the quadruplet ``2, 6, 8, 4, 6, 2``; none vanishes mod ``q >= 5``), and
    both have ``nu(2) = 1, nu(3) = 2``.  The finite check is redundant but
    cheap."""
    a, b = root_count_profile(BI_TWIN, Q), root_count_profile(QUADRUPLET, Q)
    return a == b, {q: (a[q], b[q]) for q in a}


def identity_propagation6_sextuplet(Q: int = 1000) -> tuple[bool, dict[int, tuple[int, int]]]:
    """``nu`` agrees at every prime except ``q = 7``, where the propagation
    tuple has 4 roots and the sextuplet 6; hence
    ``S_6(6) / S_sextuplet = (1 - 4/7)/(1 - 6/7) = 3`` exactly."""
    a, b = root_count_profile(PROPAGATION_6, Q), root_count_profile(SEXTUPLET, Q)
    ok = all(a[q] == b[q] for q in a if q != 7) and a[7] == 4 and b[7] == 6
    return ok, {q: (a[q], b[q]) for q in a}


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------


def format_report(ss: SingularSeries, Q: int = 10_000_000) -> str:
    r_inf = r_infinity(Q)
    bounds = propagation_ratio_bounds(r_inf)
    rbar = mean_ratio_closed_form(Q)
    kappa = kappa_closed_form(Q)
    m4 = mean_twin_pair_series(Q)
    m6 = mean_propagation_series(Q)
    L = []
    L.append("Closed forms for the local constants of the propagation conjecture")
    L.append(f"(Euler products truncated at Q = {Q:,}, analytic tail added)")
    L.append("")
    L.append("Theorem 1 (explicit local ratio)")
    L.append(f"  R_inf = 9 prod_(q>=11) q^2(q-6)/((q-1)^2(q-4))      = {r_inf:.9f}")
    L.append(f"  R_min = R_inf * 25/48 * 49/72                        = {bounds['R_min']:.9f}  (infimum over g)")
    L.append(f"  R_inf * 25/16 * 49/36                                = {bounds['R_generic_max']:.9f}  (largest value with no q>=11 | Delta(g); = R(6))")
    L.append("")
    L.append("    g     R(g) explicit    R(g) truncated product   ratio")
    for g in (6, 12, 18, 24, 30, 36, 42, 60, 90, 210, 2310, 30030, 510510):
        a = propagation_ratio_explicit(g, r_inf)
        b = ss.value(propagation_tuple(g)) / ss.value(twin_pair_tuple(g))
        L.append(f"  {g:7d}   {a:14.9f}   {b:14.9f}   {a / b:.8f}")
    L.append("")
    L.append("Theorem 2 (mean values over gaps g = 0 mod 6)")
    L.append(f"  lim (6/G) sum S_4(g) = 24 C_2^2                      = {m4:.9f}   (24 C_2^2 = {24 * TWIN_PRIME_CONSTANT ** 2:.9f})")
    L.append(f"  lim (6/G) sum S_6(g) = 24 C_2^2 Rbar                 = {m6:.9f}")
    L.append(f"  Rbar = 9 prod_(q>=5) q^2(q^2-6q+12)/((q-1)^2(q-2)^2)  = {rbar:.9f}")
    L.append(f"  kappa = 2 C_2 Rbar                                    = {kappa:.9f}   (2 C_2 Rbar = {2 * TWIN_PRIME_CONSTANT * rbar:.9f})")
    L.append("")
    L.append("  finite-height mean of R(g_n) predicted by the Hardy-Littlewood gap model")
    L.append("       x        E[R]      mean gap")
    for x in (1e6, 1e8, 1e9, 1e12, 1e20, 1e50):
        er, mg = finite_height_mean_ratio(x, ss)
        L.append(f"  {x:8.0e}   {er:9.5f}   {mg:9.1f}")
    L.append("  (observed to 10^8: 11.3480 ; to 10^9: 11.3467)")
    L.append("")
    L.append("Theorem 3 (identities)")
    ok1, prof1 = identity_bi_twin_quadruplet()
    ok2, prof2 = identity_propagation6_sextuplet()
    L.append(f"  S(n,n+2,2n+1,2n+3) = S(n,n+2,n+6,n+8): nu agrees at all q <= 1000: {ok1}; "
             f"values {ss.value(BI_TWIN):.9f} vs {ss.value(QUADRUPLET):.9f}")
    L.append(f"  S_6(6) = 3 S(n,n+4,n+6,n+10,n+12,n+16): nu agrees except at 7 ({prof2[7]}): {ok2}; "
             f"ratio {ss.value(PROPAGATION_6) / ss.value(SEXTUPLET):.9f}")
    return "\n".join(L)
