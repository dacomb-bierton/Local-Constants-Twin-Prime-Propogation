import numpy as np
import pytest

pytest.importorskip("gmpy2")

from twinconj.chain import build_chain, minimal_productive_gap  # noqa: E402
from twinconj.fastgap import (  # noqa: E402
    is_productive,
    minimal_productive_gap_fast,
    random_lower_twin,
    residues,
    sieve_primes,
)
from twinconj.primality import is_lower_twin  # noqa: E402
from twinconj.sieve import lower_twins, prime_table  # noqa: E402


def test_matches_plain_scan_on_small_twins():
    tw = lower_twins(prime_table(20_000), 12_000)
    for t in tw[tw >= 5]:
        t = int(t)
        assert minimal_productive_gap_fast(t, block=1 << 10) == minimal_productive_gap(t)


def test_residues_are_the_roots():
    t = 10**30 + 41  # any integer; residues only depend on t mod q
    primes = sieve_primes(200)
    res = residues(t, primes)
    for k, (a, b) in enumerate(((1, 0), (1, 2), (2, 1), (2, 3))):
        for i, q in enumerate(primes.tolist()):
            m = int(res[k, i])
            assert (a * t + 6 * m + b) % q == 0


def test_chain_agrees_with_reference_and_parallel_path():
    ref = build_chain(5, 30)
    t = 5
    for s in ref:
        assert minimal_productive_gap_fast(t) == s.d
        t = s.G
    # a few steps with the process pool must give the same answers
    d_par = minimal_productive_gap_fast(ref[-1].G, workers=2, block=1 << 12)
    d_seq = minimal_productive_gap_fast(ref[-1].G)
    assert d_par == d_seq and is_productive(ref[-1].G, d_seq)


def test_cap_and_random_twin():
    assert minimal_productive_gap_fast(197, cap=100) is None
    assert minimal_productive_gap_fast(197, cap=222) == 222
    rng = np.random.default_rng(1)
    t = random_lower_twin(25, rng)
    assert len(str(t)) == 25 and t % 6 == 5 and is_lower_twin(t)
