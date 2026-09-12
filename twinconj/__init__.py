"""Refined versions of the Bierton twin-prime conjectures.

Notation used throughout the package:

* ``T`` is the set of *lower twin primes*: primes ``p`` with ``p + 2`` prime.
* Every ``p in T`` with ``p > 3`` satisfies ``p == 5 (mod 6)``.
* For consecutive ``p < q`` in ``T`` with gap ``g = q - p`` the *propagation
  candidate* is ``C = p + q + 1 = 2p + g + 1``; the pair propagates when
  ``C in T``.
* An even ``d`` is a *productive gap* for ``t in T`` when ``t + d in T``,
  ``2t + d + 1 in T`` and at least one of ``d - 1``, ``d + 1`` is prime.
"""

from .sieve import prime_table, lower_twins
from .primality import is_prime, is_lower_twin

__all__ = ["prime_table", "lower_twins", "is_prime", "is_lower_twin"]
