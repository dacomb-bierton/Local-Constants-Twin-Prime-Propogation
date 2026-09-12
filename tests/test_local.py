import math

import pytest

from twinconj.local import (
    TWIN_PRIME_CONSTANT,
    SingularSeries,
    bateman_horn_integral,
    gap_series,
    gap_series_lower_bound,
    gap_tuple,
    is_admissible,
    nu,
    propagation_ratio,
    propagation_tuple,
    special_primes,
    surviving_residues,
    twin_pair_tuple,
)


@pytest.fixture(scope="module")
def ss():
    return SingularSeries(200_000)


def test_twin_constant_recovered(ss):
    assert ss.value(((1, 0), (1, 2))) == pytest.approx(2 * TWIN_PRIME_CONSTANT, rel=2e-6)


def test_prime_quadruplet_constant(ss):
    # Hardy-Littlewood constant for (n, n+2, n+6, n+8) is 4.15118...
    assert ss.value(twin_pair_tuple(6)) == pytest.approx(4.151180864, rel=1e-5)


def test_admissibility_of_propagation_tuples():
    for g in range(6, 1000, 6):
        ok, q = is_admissible(propagation_tuple(g))
        assert ok, (g, q)
    for g in (2, 4, 8, 10):
        assert not is_admissible(twin_pair_tuple(g))[0]


def test_propagation_tuple_mod5_survivors_match_note():
    # Lemma 4.2 of the original note: n = 1 (mod 5) survives for g = 6
    assert 1 in surviving_residues(propagation_tuple(6), 5)


def test_R_of_g_positive_and_zero_off_class(ss):
    assert propagation_ratio(4, ss) == 0.0
    for g in range(6, 200, 6):
        assert propagation_ratio(g, ss) > 0


def test_gap_tuple_nu5_and_admissibility():
    for t in (11, 17, 29, 41, 59, 71, 101, 107, 137):
        for s in (-1, 1):
            assert nu(gap_tuple(t, s), 5) <= 4
            assert is_admissible(gap_tuple(t, s))[0]
    assert nu(gap_tuple(5, -1), 5) == 5
    assert not is_admissible(gap_tuple(5, -1))[0]
    assert is_admissible(gap_tuple(5, 1))[0]
    assert not is_admissible(gap_tuple(3, -1))[0]


def test_uniform_lower_bound_holds_on_samples(ss):
    b = gap_series_lower_bound(200_000)
    assert 10.0 < b["S_min"] < 10.2
    for t in (11, 17, 29, 41, 59, 71, 101, 1000003 + 16):  # last one: 1000019 is a lower twin
        sm, sp, _ = gap_series(t, ss)
        assert min(sm, sp) >= b["S_min"] * (1 - 1e-6)


def test_special_primes_include_cross_differences():
    sp = special_primes(propagation_tuple(30))
    # roots of n+30 and n+2 coincide mod 7 (28 = 4*7) and mod 2
    assert 7 in sp and 2 in sp and 3 in sp and 5 in sp


def test_singular_series_direct_vs_fast_path(ss):
    # brute-force product over primes <= 2000 must agree with the cached path
    from twinconj.local import local_factor, small_primes

    forms = propagation_tuple(42)
    brute = sum(math.log(local_factor(forms, q)) for q in small_primes(2000))
    fast = SingularSeries(2000).log_value(forms, with_tail=False)
    assert brute == pytest.approx(fast, abs=1e-12)


def test_bateman_horn_integral_monotone():
    a = bateman_horn_integral(twin_pair_tuple(6), 1e6)
    b = bateman_horn_integral(twin_pair_tuple(6), 1e7)
    assert 0 < a < b
