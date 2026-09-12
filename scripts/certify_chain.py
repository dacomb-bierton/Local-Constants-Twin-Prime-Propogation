#!/usr/bin/env python3
"""Prove (not just probable-prime test) every prime in an orbit CSV with
PARI/GP, and optionally save ECPP certificates for the final pair.

    python scripts/certify_chain.py results/chain_long.csv --workers 16 \
        --ecpp results/chain_long_final.cert

For each row ``t, d, C`` the numbers ``t, t+2, t+d, t+d+2`` are proved prime
(``C, C+2`` are the next row's ``t, t+2``; the last row's ``C, C+2`` are
added), and ``C == 2t + d + 1`` and the row linkage are re-checked.  PARI's
``isprime`` is a proof for any size (APR-CL above 2^64); ``--ecpp`` runs
``primecert`` on the final ``C`` and ``C + 2`` and writes the certificates,
which anyone can check with ``primecertisvalid`` without trusting this
script.  Rows whose numbers are below 3.2e23 are already covered by the
deterministic Miller-Rabin bases of ``twinconj.primality`` but are proved
again here for uniformity.

Needs PARI/GP.  Debian/Ubuntu: ``sudo apt install pari-gp``.  Windows: run
the installer ``Pari64-2-17-4.exe`` from
https://pari.math.u-bordeaux.fr/download.html; the script then finds
``gp.exe`` under ``C:\\Program Files*\\Pari64-*`` by itself, or pass
``--gp "C:\\path\\to\\gp.exe"``.
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

GP = "gp"


def find_gp(explicit: str | None) -> str | None:
    if explicit:
        return explicit if os.path.exists(explicit) else shutil.which(explicit)
    found = shutil.which("gp")
    if found:
        return found
    if os.name == "nt":
        pats = [r"C:\Program Files*\Pari*\gp.exe", r"C:\Pari*\gp.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Pari*\gp.exe")]
        hits = sorted(h for p in pats for h in glob.glob(p))
        if hits:
            return hits[-1]
    return None


def read_rows(path: str) -> list[tuple[int, int, int]]:
    with open(path, newline="") as f:
        return [(int(r["t"]), int(r["d"]), int(r["C"])) for r in csv.DictReader(f)]


def gp_isprime_batch(nums: list[int]) -> list[bool]:
    script = "default(parisize, 256000000);\n" + "".join(f"print(isprime({n}));\n" for n in nums)
    out = subprocess.run([GP, "-q", "-f"], input=script, capture_output=True, text=True, check=True)
    vals = [line.strip() for line in out.stdout.splitlines() if line.strip() in ("0", "1")]
    if len(vals) != len(nums):
        raise RuntimeError(f"gp returned {len(vals)} results for {len(nums)} numbers: {out.stderr[:400]}")
    return [v == "1" for v in vals]


def gp_ecpp(n: int, path: str) -> bool:
    script = (f"default(parisize, 512000000);\n c = primecert({n});\n"
              f"write(\"{path}\", c);\n print(primecertisvalid(c));\n")
    out = subprocess.run([GP, "-q", "-f"], input=script, capture_output=True, text=True, check=True)
    return out.stdout.strip().splitlines()[-1] == "1"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--batch", type=int, default=40, help="numbers per gp process")
    ap.add_argument("--ecpp", help="write ECPP certificates of the final C and C+2 to this path (+'.p2')")
    ap.add_argument("--gp", help="path to the gp executable (default: search PATH and the Windows install folders)")
    a = ap.parse_args()

    global GP
    GP = find_gp(a.gp)
    if GP is None:
        print("PARI/GP not found: install it (apt install pari-gp, or the Windows installer Pari64-2-17-4.exe from\n"
              "https://pari.math.u-bordeaux.fr/download.html) or pass --gp C:\\path\\to\\gp.exe", file=sys.stderr)
        return 2
    print(f"using {GP}")
    rows = read_rows(a.csv)
    if not rows:
        print("empty file", file=sys.stderr)
        return 2

    structural = 0
    for i, (t, d, C) in enumerate(rows):
        if C != 2 * t + d + 1:
            print(f"row {i + 1}: C != 2t + d + 1"); structural += 1
        if i + 1 < len(rows) and rows[i + 1][0] != C:
            print(f"row {i + 1}: C does not link to the next t"); structural += 1
        if d % 6:
            print(f"row {i + 1}: d not divisible by 6"); structural += 1

    nums: list[tuple[int, str, int]] = []
    for i, (t, d, C) in enumerate(rows):
        nums += [(i + 1, "t", t), (i + 1, "t+2", t + 2), (i + 1, "t+d", t + d), (i + 1, "t+d+2", t + d + 2)]
    t, d, C = rows[-1]
    nums += [(len(rows), "C", C), (len(rows), "C+2", C + 2)]
    # side condition: d-1 or d+1 prime (small numbers; prove both, need one)
    side = [(i + 1, "d-1", d - 1) for i, (_, d, _) in enumerate(rows)] + [(i + 1, "d+1", d + 1) for i, (_, d, _) in enumerate(rows)]

    print(f"{len(rows)} rows: proving {len(nums)} large primes and {len(side)} side numbers with gp, {a.workers} processes")
    t0 = time.time()
    # largest numbers first so the slow ones do not trail at the end
    order = sorted(range(len(nums)), key=lambda k: -nums[k][2])
    batches = [[nums[k] for k in order[j:j + a.batch]] for j in range(0, len(order), a.batch)]
    results: dict[tuple[int, str], bool] = {}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for batch, res in zip(batches, ex.map(lambda b: gp_isprime_batch([n for _, _, n in b]), batches)):
            for (i, lab, _), ok in zip(batch, res):
                results[(i, lab)] = ok
        side_res = gp_isprime_batch([n for _, _, n in side])
    side_ok = {}
    for (i, lab, _), ok in zip(side, side_res):
        side_ok[(i, lab)] = ok

    failures = [(i, lab) for (i, lab), ok in results.items() if not ok]
    side_fail = [i for i in range(1, len(rows) + 1) if not (side_ok[(i, "d-1")] or side_ok[(i, "d+1")])]
    print(f"proved prime: {len(results) - len(failures)}/{len(results)}   side condition holds: {len(rows) - len(side_fail)}/{len(rows)}   "
          f"structural errors: {structural}   ({time.time() - t0:.1f}s)")
    for i, lab in failures:
        print(f"  NOT PRIME: row {i} {lab}")
    for i in side_fail:
        print(f"  side condition fails: row {i}")

    if a.ecpp:
        t1 = time.time()
        ok1 = gp_ecpp(C, a.ecpp)
        ok2 = gp_ecpp(C + 2, a.ecpp + ".p2")
        print(f"ECPP certificates for the final C ({len(str(C))} digits) and C+2: valid={ok1 and ok2}, "
              f"written to {a.ecpp} and {a.ecpp}.p2 ({time.time() - t1:.1f}s)")
    return 0 if not (failures or side_fail or structural) else 1


if __name__ == "__main__":
    sys.exit(main())
