"""Vectorised sieve of Eratosthenes returning a full primality lookup table.

The table is a ``numpy`` boolean array ``is_p`` with ``is_p[n] == True`` iff
``n`` is prime.  One byte per integer: sieving to ``2 * 10**8`` needs 200 MB,
which is the intended working range for the experiments in this package.
"""

from __future__ import annotations

import numpy as np


def prime_table(limit: int) -> np.ndarray:
    """Boolean table of primality for ``0 <= n <= limit``."""
    limit = int(limit)
    if limit < 1:
        return np.zeros(limit + 1, dtype=bool)
    is_p = np.ones(limit + 1, dtype=bool)
    is_p[:2] = False
    is_p[4::2] = False
    for p in range(3, int(limit**0.5) + 1, 2):
        if is_p[p]:
            is_p[p * p :: 2 * p] = False
    return is_p


def lower_twins(is_p: np.ndarray, limit: int | None = None,
                chunk: int = 50_000_000) -> np.ndarray:
    """Sorted array of lower twin primes ``p <= limit`` (``p + 2`` must be
    inside the table).  Works in chunks to keep the temporary ``and`` mask
    small when the table is large."""
    n = len(is_p) - 1
    if limit is None:
        limit = n - 2
    limit = min(int(limit), n - 2)
    parts = []
    for lo in range(0, limit + 1, chunk):
        hi = min(lo + chunk, limit + 1)
        mask = is_p[lo:hi] & is_p[lo + 2 : hi + 2]
        parts.append(np.flatnonzero(mask).astype(np.int64) + lo)
    if not parts:
        return np.zeros(0, dtype=np.int64)
    return np.concatenate(parts)
