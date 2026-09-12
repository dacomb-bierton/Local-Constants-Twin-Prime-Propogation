#!/usr/bin/env python3
"""Minimal productive gaps d(t) for *independent* random lower twins t of a
fixed number of digits, compared with the Bateman-Horn/Poisson model.

    python scripts/sample_gaps.py --digits 20 30 40 60 --samples 2000 --workers 16 \
        --out results/sample_gaps.csv

For each requested digit size the script draws ``--samples`` random lower
twins (uniform start in the decade, forward scan), computes d(t) exactly with
the sieve-accelerated scanner, and records

    digits, t, d, side, norm4 = d/((ln t)^4 ln ln t), model_mean = E[d(t)],
    survival = P(d(t) > d)  (= exp(-E_t(d)) in the Poisson model).

The summary prints, per digit size and pooled, the mean of survival (0.5
under the model), the Kolmogorov-Smirnov distance to U(0,1) with its 5 %
critical value, and sum(d)/sum(E[d]).  Unlike the orbit of the chain, these
samples are independent, so the KS test is a proper test of the model at
heights far beyond exhaustive computation.  Work is farmed out per sample
(each sample scanned single-threaded), so the run scales to all cores.

Requires gmpy2.  Restartable: existing rows in --out are kept and counted.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_HERE, ".."), _HERE, os.getcwd()):
    if os.path.isdir(os.path.join(_p, "twinconj")) and _p not in sys.path:
        sys.path.insert(0, _p)
try:
    import twinconj  # noqa: F401
except ImportError:
    sys.exit("cannot find the 'twinconj' package folder next to 'scripts\\'.\n"
             "Unpack the whole zip (it creates a folder 'twinconj' containing scripts\\, twinconj\\, tests\\, results\\),\n"
             "then run this script from inside that folder, e.g.  python scripts\\extend_chain.py ...")

from twinconj.fastgap import _is_prime, minimal_productive_gap_fast, random_lower_twin  # noqa: E402
from twinconj.gaps import model_expected_min_gap, model_survival  # noqa: E402
from twinconj.local import SingularSeries  # noqa: E402
from twinconj.verify import ks_uniform  # noqa: E402

FIELDS = ["digits", "t", "d", "side", "norm4", "model_mean", "survival"]
_SS: SingularSeries | None = None


def _init(Q: int) -> None:
    global _SS
    _SS = SingularSeries(Q)


def one_sample(args: tuple[int, int]) -> dict:
    digits, seed = args
    rng = np.random.default_rng(seed)
    t = random_lower_twin(digits, rng)
    d = minimal_productive_gap_fast(t)
    m, p = _is_prime(d - 1), _is_prime(d + 1)
    lt = math.log(t)
    return {"digits": digits, "t": t, "d": d,
            "side": "both" if (m and p) else ("d-1" if m else "d+1"),
            "norm4": f"{d / (lt**4 * math.log(max(lt, math.e))):.5f}",
            "model_mean": f"{model_expected_min_gap(t, _SS):.1f}",
            "survival": f"{model_survival(t, _SS, d)[1]:.6f}"}


def summarize(path: str) -> str:
    by = defaultdict(list)
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            by[int(r["digits"])].append(r)
    L = [f"{'digits':>6} {'n':>6} {'mean norm4':>10} {'sum d / sum E[d]':>16} {'mean surv':>9} {'KS':>7} {'KS 5%':>7}"]
    pooled = []
    for dg in sorted(by):
        rows = by[dg]
        u = [float(r["survival"]) for r in rows]
        pooled += u
        ratio = sum(int(r["d"]) for r in rows) / sum(float(r["model_mean"]) for r in rows)
        n4 = np.mean([float(r["norm4"]) for r in rows])
        L.append(f"{dg:6d} {len(rows):6d} {n4:10.4f} {ratio:16.4f} {np.mean(u):9.4f} {ks_uniform(u):7.4f} {1.358 / math.sqrt(len(u)):7.4f}")
    if pooled:
        L.append(f"{'all':>6} {len(pooled):6d} {'':>10} {'':>16} {np.mean(pooled):9.4f} {ks_uniform(pooled):7.4f} {1.358 / math.sqrt(len(pooled)):7.4f}")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--digits", type=int, nargs="+", default=[20, 30, 40])
    ap.add_argument("--samples", type=int, default=500, help="samples per digit size (total in the file)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--Q", type=int, default=1_000_000, help="singular-series prime cutoff for the model")
    ap.add_argument("--seed", type=int, default=20260911)
    ap.add_argument("--out", default="results/sample_gaps.csv")
    a = ap.parse_args()

    have = defaultdict(int)
    if os.path.exists(a.out):
        with open(a.out, newline="") as f:
            for r in csv.DictReader(f):
                have[int(r["digits"])] += 1
    else:
        with open(a.out, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()

    tasks = []
    for dg in a.digits:
        for i in range(have[dg], a.samples):
            tasks.append((dg, a.seed * 1000 + dg * 100_000 + i))
    print(f"{len(tasks)} samples to compute on {a.workers} workers -> {a.out}")
    t0 = time.time()
    done = 0
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_init, initargs=(a.Q,)) as ex:
        futs = [ex.submit(one_sample, tk) for tk in tasks]
        for fu in as_completed(futs):
            r = fu.result()
            with open(a.out, "a", newline="") as f:
                csv.DictWriter(f, fieldnames=FIELDS).writerow(r)
            done += 1
            if done % 50 == 0 or done == len(tasks):
                print(f"  {done}/{len(tasks)}  {time.time() - t0:7.1f}s", flush=True)
    print()
    print(summarize(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
