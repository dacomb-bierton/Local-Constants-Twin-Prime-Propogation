import math

import numpy as np

from twinconj.primality import is_lower_twin, is_prime, next_lower_twin
from twinconj.sieve import lower_twins, prime_table

FIRST_TWINS = [3, 5, 11, 17, 29, 41, 59, 71, 101, 107, 137, 149, 179, 191, 197, 227, 239, 269, 281, 311]


def test_prime_table_matches_trial_division():
    is_p = prime_table(2000)
    for n in range(2001):
        expected = n >= 2 and all(n % k for k in range(2, math.isqrt(n) + 1))
        assert bool(is_p[n]) == expected


def test_lower_twins_first_terms():
    is_p = prime_table(400)
    assert lower_twins(is_p, 311).tolist() == FIRST_TWINS


def test_lower_twins_chunking_is_seamless():
    is_p = prime_table(100_000)
    a = lower_twins(is_p, 99_990, chunk=1_000)
    b = lower_twins(is_p, 99_990, chunk=10**9)
    assert np.array_equal(a, b)
    assert len(a) == 1224  # pi_2(10^5)


def test_miller_rabin_against_table():
    is_p = prime_table(50_000)
    for n in range(50_000):
        assert is_prime(n) == bool(is_p[n])


def test_miller_rabin_known_pseudoprimes():
    # strong pseudoprimes to several small bases
    for n in (3215031751, 2152302898747, 3474749660383, 341550071728321, 3825123056546413051):
        assert not is_prime(n)
    assert is_prime(2**61 - 1)
    assert is_prime(1000000000000000003)


def test_next_lower_twin():
    assert next_lower_twin(1) == 3
    assert next_lower_twin(4) == 5
    assert next_lower_twin(6) == 11
    assert next_lower_twin(1000) == 1019
    assert is_lower_twin(1019)
