import numpy as np
import pytest

from twinconj.certificate import run_all
from twinconj.chain import build_chain, minimal_productive_gap
from twinconj.gaps import attach_model, minimal_productive_gaps
from twinconj.local import SingularSeries
from twinconj.primality import is_lower_twin
from twinconj.propagation import run_propagation


@pytest.fixture(scope="module")
def ss():
    return SingularSeries(200_000)


def test_propagation_small_range_matches_brute_force(ss):
    res = run_propagation(20_000, ss)
    twins = [p for p in range(3, 20_001) if is_lower_twin(p)]
    nxt = next(p for p in range(20_001, 20_500) if is_lower_twin(p))
    twins.append(nxt)
    brute = sum(1 for p, q in zip(twins, twins[1:]) if is_lower_twin(p + q + 1) or is_lower_twin(p + q + 3))
    assert res.n_pairs == len(twins) - 1
    assert res.n_success == brute
    assert res.d_branch_pairs == [(3, 5)]
    assert res.first_successes[:3] == [(3, 5, 9), (5, 11, 17), (11, 17, 29)]
    # model in the right ballpark even on a tiny range
    assert 0.5 < res.ratio < 2.0


def test_propagation_gap6_rows_consistent(ss):
    res = run_propagation(200_000, ss)
    row6 = next(r for r in res.by_gap if r.g == 6)
    assert row6.pairs == res.gap6_pairs and row6.success == res.gap6_success
    assert abs(row6.predicted - res.gap6_success_bh) / res.gap6_success_bh < 0.5


def test_minimal_gaps_match_scalar_search():
    res = minimal_productive_gaps(5_000)
    assert res.missing == []
    assert res.t[0] == 5 and res.d[0] == 6
    for t, d in zip(res.t[:60], res.d[:60]):
        assert minimal_productive_gap(int(t)) == int(d)
    # records are increasing in d
    ds = [d for _, d, _ in res.records]
    assert ds == sorted(ds) and len(set(ds)) == len(ds)


def test_t3_has_no_gap():
    assert minimal_productive_gap(3) is None
    assert minimal_productive_gap(17) == 24


def test_model_mean_is_finite(ss):
    res = minimal_productive_gaps(50_000)
    attach_model(res, ss, samples_per_block=5)
    for b in res.blocks:
        assert np.isfinite(b.model_mean) and b.model_mean > 0


def test_chain_all_lower_twins():
    chain = build_chain(5, 8)
    assert len(chain) == 8
    for s in chain:
        assert is_lower_twin(s.t) and is_lower_twin(s.G) and is_lower_twin(s.t + s.d)
        assert s.G == 2 * s.t + s.d + 1
    assert [s.t for s in chain[:4]] == [5, 17, 59, 197]


def test_certificates_pass():
    certs, ok = run_all(limit=20_000, Q=50_000)
    assert ok, [c.name for cert in certs for c in cert.checks if not c.ok]
