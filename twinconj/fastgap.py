"""Sieve-accelerated search for the minimal productive gap ``d(t)`` of a huge
lower twin ``t`` (tens to hundreds of digits), optionally over several
processes.

The plain scan in :mod:`twinconj.chain` tests every ``d = 6, 12, 18, ...``
with a primality test and becomes hopeless once ``d(t)`` reaches ``10**8``
(``t`` around 45 digits).  Here the candidates ``d = 6m`` are first sieved by
all primes ``q <= Q``: ``m`` is discarded as soon as some ``q`` divides one of

    t + d,  t + d + 2,  2t + d + 1,  2t + d + 3.

For ``t = 5 (mod 6)`` and ``d = 0 (mod 6)`` the four forms are automatically
coprime to 6, so only ``q >= 5`` are sieved.  Each ``q`` kills four residue
classes of ``m`` (fewer when two forms coincide mod ``q``), so the survivors
are a fraction ``~ prod (1 - 4/q)`` of all candidates, about ``3 * 10**-5``
for ``Q = 10**5``; only the survivors are handed to gmpy2's BPSW /
Miller-Rabin test, together with the side condition ``d - 1`` or ``d + 1``
prime.  The scan proceeds block by block in increasing ``d`` and stops at the
first block (in order) that contains a productive gap, so the result is the
*least* productive gap, exactly as in :func:`twinconj.chain.minimal_productive_gap`.

Primality of numbers above ``3.2 * 10**23`` is "probable prime" (BPSW plus
Miller-Rabin rounds); use ``scripts/certify_chain.py`` (PARI/GP) for proofs.
"""

from __future__ import annotations

import math
from concurrent.futures import ProcessPoolExecutor
from typing import Iterable

import numpy as np

try:
    import gmpy2
except ImportError as exc:  # pragma: no cover
    raise ImportError("twinconj.fastgap needs gmpy2 (pip install gmpy2)") from exc

from .sieve import prime_table

DEFAULT_Q = 100_000
DEFAULT_BLOCK = 1 << 21          # m-values per sieve block (2 MB of bools)
MR_REPS = 30

_FORMS = ((1, 0), (1, 2), (2, 1), (2, 3))   # (a, b): a*t + d + b


def _is_prime(n: int) -> bool:
    return bool(gmpy2.is_prime(n, MR_REPS))


def is_productive(t: int, d: int) -> bool:
    """Full definition: side condition and four primality tests."""
    return (_is_prime(d - 1) or _is_prime(d + 1)) and _is_prime(t + d) and _is_prime(t + d + 2) \
        and _is_prime(2 * t + d + 1) and _is_prime(2 * t + d + 3)


def sieve_primes(Q: int) -> np.ndarray:
    """Primes ``5 <= q <= Q`` as an int64 array."""
    tab = prime_table(Q)
    tab[:5] = False
    return np.flatnonzero(tab).astype(np.int64)


def residues(t: int, primes: np.ndarray) -> np.ndarray:
    """``res[k, i]`` = the class of ``m`` (mod ``primes[i]``) for which prime
    ``primes[i]`` divides form ``k`` at ``d = 6m``:  ``6m = -(a t + b)``."""
    t_mod = np.array([int(t % int(q)) for q in primes], dtype=np.int64)
    q = primes
    inv6 = np.array([pow(6, -1, int(p)) for p in primes], dtype=np.int64)
    res = np.empty((4, len(primes)), dtype=np.int64)
    for k, (a, b) in enumerate(_FORMS):
        res[k] = ((-(a * t_mod + b)) % q) * inv6 % q
    return res


def scan_block(t: int, m_lo: int, m_hi: int, primes: np.ndarray, res: np.ndarray) -> int | None:
    """Least productive ``d = 6m`` with ``m_lo <= m < m_hi``, or ``None``.

    The sieve is only valid when every form value exceeds every sieving
    prime, i.e. ``t + 6 m_lo > Q``; callers guarantee this by choosing
    ``Q < t`` (``m_lo >= 1``)."""
    n = m_hi - m_lo
    alive = np.ones(n, dtype=bool)
    for k in range(4):
        starts = (res[k] - m_lo) % primes
        for s, q in zip(starts.tolist(), primes.tolist()):
            alive[s::q] = False
    for m in (np.flatnonzero(alive) + m_lo).tolist():
        d = 6 * m
        if is_productive(t, d):
            return d
    return None


def _worker(args):
    return scan_block(*args)


def minimal_productive_gap_fast(t: int, Q: int = DEFAULT_Q, block: int = DEFAULT_BLOCK,
                                workers: int = 1, cap: int | None = None,
                                executor: ProcessPoolExecutor | None = None) -> int | None:
    """Least productive gap of the lower twin ``t >= 5``.

    ``workers > 1`` scans ``workers`` consecutive blocks at a time in a
    process pool; the minimum over a round of blocks is the global minimum
    because every earlier round was empty.  ``cap`` stops the search once
    ``d > cap`` (returns ``None``)."""
    t = int(t)
    if t == 5:
        return 6
    if t == 3:
        return None
    Q = min(int(Q), t - 1)
    if Q < 5:
        primes = np.zeros(0, dtype=np.int64)
    else:
        primes = sieve_primes(Q)
    res = residues(t, primes)
    m = 1
    own = None
    if workers > 1 and executor is None:
        own = executor = ProcessPoolExecutor(max_workers=workers)
    try:
        while cap is None or 6 * m <= cap:
            if workers > 1:
                tasks = []
                for _ in range(workers):
                    tasks.append((t, m, m + block, primes, res))
                    m += block
                found = [d for d in executor.map(_worker, tasks) if d is not None]
                if found:
                    d = min(found)
                    return None if (cap is not None and d > cap) else d
            else:
                d = scan_block(t, m, m + block, primes, res)
                if d is not None:
                    return None if (cap is not None and d > cap) else d
                m += block
        return None
    finally:
        if own is not None:
            own.shutdown()


def random_lower_twin(digits: int, rng: np.random.Generator) -> int:
    """A lower twin prime with exactly ``digits`` decimal digits, found by a
    random start and a forward scan over the class ``5 (mod 6)``."""
    lo, hi = 10 ** (digits - 1), 10**digits
    while True:
        # uniform big integer in [lo, hi): 30 random bits at a time
        n = 0
        for _ in range(digits // 9 + 1):
            n = (n << 30) | int(rng.integers(0, 1 << 30))
        n = lo + n % (hi - lo - 10**6)
        t = n + ((5 - n) % 6)
        while t < hi:
            if _is_prime(t) and _is_prime(t + 2):
                return t
            t += 6


def expected_norm4(t: int, d: int) -> float:
    lt = math.log(t)
    return d / (lt**4 * math.log(max(lt, math.e)))


def chain_from(t: int, steps: int, **kw) -> Iterable[tuple[int, int, int]]:
    """Yield ``(t, d, C)`` for ``steps`` consecutive applications of
    ``t -> 2t + d(t) + 1`` starting at ``t``."""
    for _ in range(steps):
        d = minimal_productive_gap_fast(t, **kw)
        if d is None:
            return
        C = 2 * t + d + 1
        yield t, d, C
        t = C
