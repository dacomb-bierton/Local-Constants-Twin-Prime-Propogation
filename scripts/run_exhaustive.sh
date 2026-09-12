#!/usr/bin/env bash
# Exhaustive experiments at the largest heights that fit a 128 GB machine.
# All numbers below are memory estimates for the numpy tables (1 byte per
# integer, two tables of size ~2*limit); times are extrapolated from the
# reference runs in results/ (1e8 in ~1 min on one core).  Both commands are
# single-threaded, so run them concurrently with scripts/extend_chain.py and
# scripts/sample_gaps.py, which use the other cores.
#
#   bash scripts/run_exhaustive.sh            # gaps 1e10 + propagation 1e10
#   bash scripts/run_exhaustive.sh 1e9        # smaller rehearsal (~5 GB, ~15 min)
set -euo pipefail
cd "$(dirname "$0")/.."
LIMIT="${1:-1e10}"
mkdir -p results

echo "== gaps --limit $LIMIT   (RAM ~ 4 bytes * limit -> 1e10: ~40 GB; ~1-3 h)"
python3 -m twinconj gaps --limit "$LIMIT" --model --out "results/gaps_${LIMIT}.txt"

echo "== propagation --limit $LIMIT   (RAM ~ 2 bytes * limit -> 1e10: ~20 GB; ~30-60 min)"
python3 -m twinconj propagation --limit "$LIMIT" --out "results/propagation_${LIMIT}.txt"

echo "done; outputs in results/gaps_${LIMIT}.txt and results/propagation_${LIMIT}.txt"
