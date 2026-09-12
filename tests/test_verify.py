import csv

from twinconj.chain import build_chain
from twinconj.local import SingularSeries
from twinconj.verify import attach_model, format_chain_verification, ks_uniform, verify_chain_csv


def _write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["step", "t", "d", "C", "adjacency"])
        w.writerows(rows)


def test_own_chain_verifies(tmp_path):
    chain = build_chain(5, 12)
    p = tmp_path / "chain.csv"
    _write(p, [(s.step, s.t, s.d, s.G, 0) for s in chain])
    rows = verify_chain_csv(str(p))
    assert len(rows) == 12 and all(r.ok and r.minimal for r in rows)
    assert "steps failing a check: 0" in format_chain_verification(str(p), rows)


def test_non_minimal_and_broken_link_are_flagged(tmp_path):
    # (197, 462) is productive (659, 857 lower twins; 461, 463 prime) but d(197) = 222
    rows_in = [(1, 5, 6, 17, 3), (2, 17, 24, 59, 1), (3, 59, 78, 197, 2), (4, 197, 462, 857, 3), (5, 859, 6, 1725, 0)]
    p = tmp_path / "chain.csv"
    _write(p, rows_in)
    rows = verify_chain_csv(str(p))
    assert [r.ok for r in rows[:3]] == [True, True, True]
    assert rows[3].minimal is False and rows[3].least_d == 222 and rows[3].ok_link is False
    assert rows[4].ok_t is False and rows[4].ok is False


def test_model_columns_and_ks(tmp_path):
    chain = build_chain(5, 8)
    p = tmp_path / "chain.csv"
    _write(p, [(s.step, s.t, s.d, s.G, 0) for s in chain])
    rows = verify_chain_csv(str(p), check_minimal=False)
    attach_model(rows, SingularSeries(10_000))
    assert all(r.model_mean is not None and 0.0 < r.survival <= 1.0 for r in rows)
    # E_t(d) is increasing in d, so the survival of a larger gap is smaller
    assert rows[0].model_mean > 6
    text = format_chain_verification(str(p), rows)
    assert "P(d(t)>d)" in text and "KS distance" in text
    assert ks_uniform([]) == 0.0
    assert abs(ks_uniform([0.25, 0.75]) - 0.25) < 1e-12
    assert abs(ks_uniform([0.0, 0.0, 0.0]) - 1.0) < 1e-12


def test_model_beyond_double_range():
    from twinconj.gaps import model_expected_min_gap, model_survival
    ss = SingularSeries(10_000)
    t = 10**320 + 1  # = 5 (mod 6); float(t) would overflow
    m = model_expected_min_gap(t, ss)
    assert 1e9 < m < 1e13
    e, u = model_survival(t, ss, int(m))
    assert 0.5 < e < 2.0 and 0.1 < u < 0.7
