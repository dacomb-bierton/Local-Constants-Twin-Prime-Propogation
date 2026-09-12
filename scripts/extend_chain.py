#!/usr/bin/env python3
"""Extend the constructive orbit  t -> 2t + d(t) + 1  with exact minimal
productive gaps, resumably, using all CPU cores.

    python scripts/extend_chain.py --csv results/chain_long.csv --steps 1000 --workers 16

* If ``--csv`` exists, the run resumes from its last row (``C`` of the last
  row is the next ``t``); otherwise it starts from ``t = 5`` (or ``--start``).
* Every completed step is appended to the CSV immediately, so the run can be
  interrupted at any time and restarted with the same command.
* Columns: step, t, d, C, side, digits, norm4  (norm4 = d / ((ln t)^4 ln ln t)).
* ``--from-chain twin_gap_chain.csv`` seeds a new CSV from an existing orbit
  file (e.g. the 150-step file of the original generator) instead of t = 5.

Requires gmpy2.  Primality above 3.2e23 is probable-prime (BPSW + 30 MR
rounds); certify a finished file with scripts/certify_chain.py.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

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

from twinconj.fastgap import DEFAULT_BLOCK, DEFAULT_Q, _is_prime, minimal_productive_gap_fast  # noqa: E402

FIELDS = ["step", "t", "d", "C", "side", "digits", "norm4"]


def read_last(path: str) -> tuple[int, int] | None:
    """(step, C) of the last row, or None if the file is empty/missing."""
    if not os.path.exists(path):
        return None
    last = None
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            last = r
    if last is None:
        return None
    return int(last["step"]), int(last["C"])


def seed_from(chain_csv: str, out_csv: str) -> None:
    with open(chain_csv, newline="") as f, open(out_csv, "w", newline="") as g:
        w = csv.DictWriter(g, fieldnames=FIELDS)
        w.writeheader()
        for r in csv.DictReader(f):
            t, d, C = int(r["t"]), int(r["d"]), int(r["C"])
            w.writerow(row(int(r["step"]), t, d, C))


def row(step: int, t: int, d: int, C: int) -> dict:
    m, p = _is_prime(d - 1), _is_prime(d + 1)
    lt = math.log(t)
    return {"step": step, "t": t, "d": d, "C": C,
            "side": "both" if (m and p) else ("d-1" if m else "d+1"),
            "digits": len(str(t)),
            "norm4": f"{d / (lt**4 * math.log(max(lt, math.e))):.5f}"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default="results/chain_long.csv")
    ap.add_argument("--steps", type=int, default=1000, help="target total number of steps in the file")
    ap.add_argument("--start", type=int, default=5)
    ap.add_argument("--from-chain", help="seed the CSV from an existing orbit file (step,t,d,C)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--Q", type=int, default=DEFAULT_Q, help="sieve primes up to Q")
    ap.add_argument("--block", type=int, default=DEFAULT_BLOCK, help="m-values per sieve block")
    ap.add_argument("--max-hours", type=float, default=None, help="stop cleanly after this many hours")
    a = ap.parse_args()

    if a.from_chain and not os.path.exists(a.csv):
        seed_from(a.from_chain, a.csv)
        print(f"seeded {a.csv} from {a.from_chain}")

    last = read_last(a.csv)
    if last is None:
        step, t = 0, a.start
        if not (_is_prime(t) and _is_prime(t + 2)) or t < 5:
            print("start must be a lower twin prime >= 5", file=sys.stderr)
            return 2
        with open(a.csv, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
    else:
        step, t = last
    print(f"resuming at step {step + 1}: t has {len(str(t))} digits; {a.workers} workers, Q={a.Q}, block={a.block}")

    t_start = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        while step < a.steps:
            if a.max_hours is not None and time.time() - t_start > 3600 * a.max_hours:
                print("time budget reached; rerun the same command to continue")
                break
            t0 = time.time()
            d = minimal_productive_gap_fast(t, Q=a.Q, block=a.block, workers=a.workers, executor=ex)
            if d is None:
                print(f"no productive gap found for t={t} (this would contradict the conjecture)")
                return 1
            C = 2 * t + d + 1
            step += 1
            r = row(step, t, d, C)
            with open(a.csv, "a", newline="") as f:
                csv.DictWriter(f, fieldnames=FIELDS).writerow(r)
            print(f"step {step:5d}  digits {r['digits']:4d}  d={d:>16,}  side {r['side']:4s}  norm4 {r['norm4']}  "
                  f"{time.time() - t0:7.1f}s", flush=True)
            t = C
    print(f"done: {step} steps in {a.csv}; last t has {len(str(t))} digits; {(time.time() - t_start) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
