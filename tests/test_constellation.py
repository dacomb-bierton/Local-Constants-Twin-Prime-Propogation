import pytest

from twinconj.constellation import PRESETS, forms_to_str, parse_forms, run_constellation
from twinconj.local import SingularSeries
from twinconj.primality import is_prime


@pytest.fixture(scope="module")
def ss():
    return SingularSeries(200_000)


def test_parse_forms():
    assert parse_forms("n, n+2, 2n+7, 3*n - 4") == ((1, 0), (1, 2), (2, 7), (3, -4))
    assert forms_to_str(((1, 0), (2, 7), (1, -3))) == "n, 2n+7, n-3"
    with pytest.raises(ValueError):
        parse_forms("n, n")
    with pytest.raises(ValueError):
        parse_forms("0n+1")


def test_all_presets_admissible_and_parse():
    for spec, _ in PRESETS.values():
        forms = parse_forms(spec)
        assert len(forms) >= 2


def test_twin_count_matches_brute_force(ss):
    res = run_constellation(parse_forms("n, n+2"), 100_000, ss, chunk=7_777)
    brute = sum(1 for n in range(2, 100_001) if is_prime(n) and is_prime(n + 2))
    assert res.count == brute == 1224
    assert res.first[:5] == [3, 5, 11, 17, 29]
    assert 0.9 < res.ratio < 1.1
    assert res.sieve_upper_bound > res.count
    assert sum(b.count for b in res.blocks) == res.count


def test_sophie_germain_brute_force(ss):
    res = run_constellation(parse_forms("n, 2n+1"), 50_000, ss)
    brute = sum(1 for n in range(2, 50_001) if is_prime(n) and is_prime(2 * n + 1))
    assert res.count == brute


def test_non_admissible_rejected(ss):
    with pytest.raises(ValueError):
        run_constellation(parse_forms("n, n+1"), 1000, ss)
