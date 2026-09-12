"""Exact primality for individual integers.

Uses ``gmpy2`` when installed.  Otherwise a deterministic Miller-Rabin test
with the first twelve prime bases is used, which is a proof of primality for
every ``n < 3.18 * 10**23`` (Sorenson-Webster, 2015); this comfortably covers
``2**64``.  The original repositories used the base set ``(2,3,5,7,11,13,23)``
and labelled it deterministic below ``2**64``; that base set is not among the
published deterministic sets, so it is not relied on here.
"""

from __future__ import annotations

_SMALL_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
_MR_BASES = _SMALL_PRIMES
_DETERMINISTIC_LIMIT = 318_665_857_834_031_151_167_461

try:  # pragma: no cover - depends on optional dependency
    import gmpy2 as _gmpy2

    def is_prime(n: int) -> bool:
        n = int(n)
        if n < 2:
            return False
        # GMP's mpz_probab_prime_p: trial division, BPSW, then the requested
        # Miller-Rabin rounds.  Deterministic below the limit; above it a
        # probable-prime test, as the pure-Python fallback would be.
        return bool(_gmpy2.is_prime(n, 25 if n < _DETERMINISTIC_LIMIT else 40))

except ImportError:  # pragma: no cover

    def is_prime(n: int) -> bool:
        return _miller_rabin(int(n))


def _miller_rabin(n: int) -> bool:
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n == p:
            return True
        if n % p == 0:
            return False
    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in _MR_BASES:
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def is_lower_twin(p: int) -> bool:
    p = int(p)
    return p > 1 and is_prime(p) and is_prime(p + 2)


def next_lower_twin(n: int) -> int:
    """Smallest lower twin prime ``>= n``."""
    n = int(n)
    if n <= 3:
        return 3
    if n <= 5:
        return 5
    # All lower twins above 3 are 5 (mod 6).
    t = n + ((5 - n) % 6)
    while not is_lower_twin(t):
        t += 6
    return t
