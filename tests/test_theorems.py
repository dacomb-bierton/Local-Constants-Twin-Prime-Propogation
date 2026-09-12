import math

import pytest

from twinconj import theorems as th
from twinconj.local import (
    TWIN_PRIME_CONSTANT,
    SingularSeries,
    nu,
    propagation_mean_ratio_model,
    propagation_ratio,
    propagation_tuple,
    small_primes,
    twin_pair_tuple,
)


@pytest.fixture(scope="module")
def ss():
    return SingularSeries(Q=300_000)


def test_root_count_table_matches_enumeration():
    for g in range(6, 1201, 6):
        for q in (5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
            assert th.nu4_gap(g, q) == nu(twin_pair_tuple(g), q)
            assert th.nu6_gap(g, q) == nu(propagation_tuple(g), q)


def test_explicit_ratio_matches_direct_product(ss):
    r_inf_bare = th.r_infinity(Q=ss.Q, tail=False)
    for g in (6, 12, 30, 42, 210, 2310, 30030, 510510):
        direct = math.exp(ss.log_value(propagation_tuple(g), with_tail=False)
                          - ss.log_value(twin_pair_tuple(g), with_tail=False))
        assert th.propagation_ratio_explicit(g, r_inf_bare) == pytest.approx(direct, rel=1e-11)
        # with tails the two estimates differ only by the tail refinement, O(1/(Q log^2 Q))
        assert th.propagation_ratio_explicit(g, th.r_infinity(Q=ss.Q)) == pytest.approx(
            propagation_ratio(g, ss), rel=1e-6)


def test_r6_is_r_inf_times_small_prime_factors():
    r_inf = th.r_infinity(Q=200_000)
    assert th.propagation_ratio_explicit(6, r_inf) == pytest.approx(r_inf * 25 / 16 * 49 / 36, rel=1e-12)


def test_lower_bound_is_infimum_not_attained():
    b = th.propagation_ratio_bounds(th.r_infinity(Q=200_000))
    assert b["R_min"] == pytest.approx(2.08358, abs=2e-5)
    vals = [th.propagation_ratio_explicit(g, b["R_inf"]) for g in range(6, 60_001, 6)]
    assert min(vals) > b["R_min"]
    # g = 0 (mod 5), g = +-2 (mod 7), and every prime dividing Delta(g) is < 11 -> only g = 6 qualifies
    # for the small-prime part, but 6 = 1 (mod 5), so the infimum is never attained
    assert all(th.gamma(q) < th.rho(g, q) for q in (11, 13, 101) for g in range(1, 60) if th.delta(g) % q == 0)


def test_mean_local_factors():
    for q in [q for q in small_primes(100) if q >= 5]:
        assert th.mean_local_factor(4, q) == pytest.approx((q - 2) ** 2 / q**2 * (1 - 1 / q) ** -4)
        assert th.mean_local_factor(6, q) == pytest.approx((q * q - 6 * q + 12) / q**2 * (1 - 1 / q) ** -6)


def test_closed_form_constants():
    Q = 2_000_000
    assert th.mean_twin_pair_series(Q) == pytest.approx(24 * TWIN_PRIME_CONSTANT**2, rel=1e-7)
    rbar = th.mean_ratio_closed_form(Q)
    assert rbar == pytest.approx(11.18490, abs=2e-5)
    assert rbar == pytest.approx(propagation_mean_ratio_model(Q=20_000), rel=2e-5)
    assert th.kappa_closed_form(Q) == pytest.approx(2 * TWIN_PRIME_CONSTANT * rbar, rel=1e-7)
    assert th.mean_propagation_series(Q) == pytest.approx(th.mean_twin_pair_series(Q) * rbar, rel=1e-7)


def test_partial_means_converge(ss):
    G = 30_000
    s4 = sum(ss.value(twin_pair_tuple(g)) for g in range(6, G + 1, 6)) / (G // 6)
    assert s4 == pytest.approx(24 * TWIN_PRIME_CONSTANT**2, rel=0.01)


def test_finite_height_mean_matches_observation(ss):
    er9, gap9 = th.finite_height_mean_ratio(1e9, ss)
    assert er9 == pytest.approx(11.3467, abs=0.02)   # observed mean of R(g_n) to 1e9
    er_big, _ = th.finite_height_mean_ratio(1e40, ss)
    assert abs(er_big - 11.1849) < abs(er9 - 11.1849)


def test_identities(ss):
    ok, prof = th.identity_bi_twin_quadruplet()
    assert ok and prof[2] == (1, 1) and prof[3] == (2, 2)
    assert ss.value(th.BI_TWIN) == pytest.approx(ss.value(th.QUADRUPLET), rel=1e-12)
    ok, prof = th.identity_propagation6_sextuplet()
    assert ok and prof[7] == (4, 6)
    assert ss.value(th.PROPAGATION_6) / ss.value(th.SEXTUPLET) == pytest.approx(3.0, rel=1e-12)


def test_delta_prime_factors():
    assert th._prime_factors_ge(th.delta(6), 11) == []
    assert th._prime_factors_ge(th.delta(12), 11) == [11, 13]
    assert math.prod(th._prime_factors_ge(th.delta(30), 11)) == 11 * 29 * 31
