# twinconj — refined twin-prime conjectures

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

Repository: [https://github.com/dacomb-bierton/Local-Constants-Twin-Prime-Propogation](https://github.com/dacomb-bierton/Local-Constants-Twin-Prime-Propogation)

**Dacomb Bierton**  
ORCID: [0009-0007-7507-1398](https://orcid.org/0009-0007-7507-1398)

Sharpened versions of the three statements in Dacomb Bierton's notes on
lower twin primes — the **Twin-Prime Propagation Conjecture**, the
**Twin-Gap Existence Conjecture**, and their **structural reduction** to
Hypothesis H / Bateman–Horn — plus the code that tests them.

The mathematics (new statements, new lemmas with proofs, data, and a list of
issues found in the original repositories) is in
**[REFINED_CONJECTURES.md](REFINED_CONJECTURES.md)**.  In one paragraph:

* **A′** turns "infinitely many propagating pairs" into an asymptotic with an
  explicit local factor `R(g)` and constant `κ = 2·C₂·R̄ = 14.76768…`;
  it is verified to `p ≤ 10¹⁰` with actual/predicted = 1.0044.
* **B′** turns "a productive gap `d = o(t)` for large `t`" into
  `d(t) ≤ (log t)⁵ log log t` for every lower twin `t ≥ 5` (with `t = 3`
  proved to be the only exception), plus a Poisson model for the
  distribution of `d(t)` that matches block means to a few percent up to
  `t ≤ 10¹⁰`, passes a KS test on 14,000 independent random twins of
  20–150 digits, and is followed by a proved 1,134-step orbit to 343 digits.
* **C′** removes the "thin exceptional set" from the conditional theorem
  (admissibility for every `t ≥ 11`), replaces `S(t) ≫ (log t)^{-O(1)}` by
  an absolute lower bound `S(t) ≥ 10.1315…`, and corrects the claim that B is
  stronger than A (they are formally incomparable).

**[paper/bierton_local_constants.tex](paper/bierton_local_constants.tex)**
(PDF alongside) is a paper draft with full proofs of the *unconditional*
results that came out of this: an explicit finite-product formula for
`R(g)` with the sharp bounds `2.0836 < R(g) ≪ (log log g)²`; the mean values
`(6/G)·Σ S₄(g) → 24 C₂²` and `(6/G)·Σ S₆(g) → 24 C₂² R̄` with
`R̄ = 9·∏_{q≥5} q²(q²−6q+12)/((q−1)²(q−2)²) = 11.18490…`, which pins down
`κ`; the unconditional bound `N(X) ≪ X/(log X)³` for propagating pairs; and
the identities "bi-twin chains have the singular series of prime
quadruplets" and "`S₆(6) = 3·S(sextuplet)`".  `python -m twinconj theorems`
prints the constants; `certify` re-checks every finite step.

**[WHAT_CAN_BE_PROVED.md](WHAT_CAN_BE_PROVED.md)** separates what is proved
(unconditional lemmas, Selberg upper bounds of the right order, conditional
theorems) from what is only predicted, explains why none of it can yield a
proof of the twin prime conjecture by contradiction (parity barrier,
Proposition 8), and shows how the same machinery produces tested
quantitative conjectures for any related constellation
(`twinconj constellation`).

## Install and run

Python ≥ 3.10 and `numpy`.  `gmpy2` is optional (faster primality for the
big-integer chain generator).

```bash
pip install -e .            # or: pip install -r requirements.txt
python -m twinconj certify                    # machine-check Lemmas 1-7 and Theorems 1-3
python -m twinconj constants                  # R(g) table, S_min, κ model value
python -m twinconj theorems                   # closed-form constants R_inf, R_min, R̄, κ; identities
python -m twinconj propagation --limit 1e8    # Conjecture A' : actual vs predicted
python -m twinconj gaps --limit 1e7 --model   # Conjecture B' : minimal gaps d(t)
python -m twinconj chain --steps 25           # orbit t -> 2t + d(t) + 1, exact minimal gaps
python -m twinconj verify-chain twin_gap_chain.csv   # re-check an orbit CSV from final.py/main.py (primality, links, minimality, Poisson-model E[d(t)] and P(d(t)>d))
python -m twinconj constellation --list       # any linear-form tuple: count vs Bateman-Horn vs Selberg bound
python -m twinconj constellation --preset bi-twin --limit 1e8   # bi-twin chains (OEIS A066388)
pytest                                        # unit tests
```

`propagation --limit 1e9` needs about 2 GB of RAM and a minute,
`gaps --limit 1e8 --model` about 30 s; the `1e10` runs need 20 GB and 40 GB
(see "Running at scale").  Reference output for all of them is in
[`results/`](results/).

## Layout

| path | contents |
|---|---|
| `twinconj/sieve.py` | numpy sieve → boolean primality table, lower-twin extraction |
| `twinconj/primality.py` | deterministic Miller–Rabin (12 bases, proven below 3.18·10²³), optional gmpy2 |
| `twinconj/local.py` | linear-form tuples, admissibility, singular series with cached generic products, `R(g)`, the uniform lower bound `S_min`, Bateman–Horn integrals, the model value of `E[R]` |
| `twinconj/propagation.py` | Conjecture A′ experiment: propagating pairs vs prediction, dyadic and gap-resolved tables, gap-6 Bateman–Horn check |
| `twinconj/gaps.py` | Conjecture B′ experiment: exact `d(t)` for all `t ≤ X`, records, normalised statistics, Poisson-model means |
| `twinconj/chain.py` | constructive orbit with arbitrary-precision integers |
| `twinconj/verify.py` | independent verification of orbit CSVs produced by the original generators, with per-step Poisson-model expectation and survival probability (`results/verify_twin_gap_chain_150.txt`) |
| `twinconj/fastgap.py` | sieve-accelerated, multi-process minimal productive gap for huge `t` (gmpy2); random lower twins of a given size |
| `scripts/` | `extend_chain.py`, `sample_gaps.py`, `certify_chain.py` (PARI/GP), `run_exhaustive.sh`: the large-machine runs described above |
| `twinconj/theorems.py` | closed forms: explicit `R(g)`, `R_inf`, `R_min`, mean values, `R̄`, `κ`, finite-height mean, singular-series identities |
| `twinconj/constellation.py` | generic constellation counter with Bateman–Horn prediction and Selberg upper bound; presets for related conjectures |
| `twinconj/certificate.py` | finite residue proofs / witnesses for every lemma in the note |
| `twinconj/cli.py` | command line |
| `tests/` | pytest suite |
| `results/` | output of the runs quoted in the note |
| `paper/` | LaTeX source and PDF of the paper draft (compile with `tectonic` or `pdflatex`) |

## Running at scale (`scripts/`)

The Python loop in `twinconj chain` stops being practical near 45 digits.
`twinconj/fastgap.py` sieves the candidates `d = 6m` by all primes up to
`10^5` (four residue classes of `m` per prime) before any primality test, and
scans blocks of `d` in parallel; it reproduces the 150-step chain in 6 s and
reaches 400 steps (123 digits) in under 2 minutes on 4 cores.  The scripts
below are built on it and are all resumable.

```bash
pip install gmpy2                     # required by the scripts
sudo apt install pari-gp              # Linux/WSL; on Windows run Pari64-2-17-4.exe from pari.math.u-bordeaux.fr (see scripts/RUN.md)

# 1. extend the orbit; appends to the CSV after every step, resume with the same command
python scripts/extend_chain.py --csv results/chain_long.csv --steps 1000 --workers 15

# 2. independent random twins of fixed size, d(t) vs the Poisson model (proper KS test)
python scripts/sample_gaps.py --digits 20 30 40 60 80 100 --samples 2000 --workers 15 --out results/sample_gaps.csv

# 3. prove every prime of a chain file (t, t+2, t+d, t+d+2, C, C+2, side condition) and write ECPP certificates
python scripts/certify_chain.py results/chain_long.csv --workers 15 --ecpp results/chain_long_final.cert

# 4. exhaustive d(t) and propagation counts to 1e10 (~40 GB RAM, single-threaded; run alongside 1-2)
bash scripts/run_exhaustive.sh 1e10
```

Rough costs on a 16-core desktop with 128 GB: step 1 to 1000 steps (300
digits) is an hour or two, and continues to ~1500 steps overnight; step 2 at
100 digits is well under a second per sample, at 200 digits about a minute
per sample per core; step 3 proves 1,600 primes of up to 123 digits in 12 s;
step 4 at `1e10` needs about 40 GB for `gaps` and 20 GB for `propagation`
and finishes in well under an hour each (`3e8` takes 30 s).  `2e10` is the
practical ceiling for `gaps` (80 GB).  The GPU is not used by any of this.

Results of these runs on a 5950X / 128 GB machine are in `results/`:

* `chain_long.csv`: 1,134 steps of the orbit (5 → 343 digits), every one of
  its 4,538 large primes proved with PARI's APR-CL
  (`chain_long_certify.txt`), ECPP certificates for the final pair
  (`chain_long_final.cert*`), Poisson-model comparison in
  `verify_chain_long.txt` (mean survival 0.516, KS 0.038 against a 5 %
  critical value of 0.040).
* `sample_gaps.csv`: 14,000 independent random lower twins of 20–150 digits
  with exact `d(t)`; pooled KS distance to the model 0.0086 (critical 0.0115),
  see `sample_gaps_summary_14000.txt`.
* `gaps_1e10.txt`: exact `d(t)` for all 27,412,678 twins to 10¹⁰ (none
  missing, max `d` = 1,728,906, B′ ratio at most 0.144).
* `propagation_1e10.txt`: 615,447 propagating pairs to 10¹⁰ against
  612,777 predicted (ratio 1.0044).

## Verification of the original generators

The generators behind the *Twin-Gap Existence* note (`final.py`, `main.py`,
`ingredient_B_test.py`) were re-checked here with `verify-chain`:

* `twin_gap_chain.csv` (`final.py`, 150 steps, 5 → a 47-digit `t`): every
  step is a valid propagation with the side condition, every `C` links to
  the next `t`, and every `d` is the **least** productive gap, so the file is
  the orbit of `d(t)` and agrees with `python -m twinconj chain --steps 150`.
  The normalised gaps `d / ((ln t)^4 ln ln t)` average 0.046 over the 115
  steps with `t > 10^12` (exhaustive mean to 10^8: 0.0575), and the
  Poisson model `P(d(t) > Y) = exp(-E_t(Y))` is calibrated along the orbit:
  mean survival `P(d(t) > d_observed) = 0.497`, KS distance to `U(0,1)`
  0.057 (5 % critical value 0.111).  See
  [`results/verify_twin_gap_chain_150.txt`](results/verify_twin_gap_chain_150.txt).
  All 602 large primes and the 150 side conditions are *proved* (APR-CL via
  PARI) in [`results/twin_gap_chain_150_certify.txt`](results/twin_gap_chain_150_certify.txt),
  so the chain no longer rests on probable-prime tests.
* `generated_twins.csv` (`main.py`, 60 steps) is a valid orbit but **not** the
  orbit of `d(t)`: `main.py` tries a preferred list of gaps first, and steps
  4 and 6 use `d = 462` where the least productive gaps are 222 and 264.
  See [`results/verify_generated_twins_60.txt`](results/verify_generated_twins_60.txt).
* `ingredient_B_test.csv` tests `d(t) <= t^0.8`, not `t^0.5`.  The exhaustive
  table in [`results/gaps_1e8.txt`](results/gaps_1e8.txt) shows that
  `d(t) <= t^theta` fails for 259,417 twins `t <= 10^8` at `theta = 0.5`
  (largest 99,999,077), for 2,789 at `theta = 0.7` and for 206 at
  `theta = 0.8` (largest 5,165,387).  Since `d(t)` is typically of size
  `0.06 (ln t)^4 ln ln t`, which exceeds `sqrt t` until `t ~ 10^10`, a
  power-law bound is only the right comparison for large `t`; the
  `(ln t)^4 ln ln t` law is the one the data follow across all 46 orders of
  magnitude of the chain.

## Citation

Please cite this repository together with Bierton's Zenodo preprints:

* D. Bierton, *A twin-prime propagation conjecture*, [10.5281/zenodo.22017371](https://doi.org/10.5281/zenodo.22017371)
* D. Bierton, *A twin-gap existence conjecture*, [10.5281/zenodo.22058355](https://doi.org/10.5281/zenodo.22058355)
* D. Bierton, *Structural reduction of two twin-prime conjectures…*, [10.5281/zenodo.22063097](https://doi.org/10.5281/zenodo.22063097)
* D. Bierton, *Theorems on twin-prime propagation…*, [10.5281/zenodo.22206095](https://doi.org/10.5281/zenodo.22206095)

A GitHub release `v1.0` is published so Zenodo can archive this repository the same way as the earlier code deposits ([10.5281/zenodo.22040224](https://doi.org/10.5281/zenodo.22040224), [10.5281/zenodo.22058546](https://doi.org/10.5281/zenodo.22058546), [10.5281/zenodo.22063114](https://doi.org/10.5281/zenodo.22063114)). Once this repository is enabled at [Zenodo’s GitHub settings](https://zenodo.org/account/settings/github/) and archived, the software DOI will be added here and in `CITATION.cff`.

## Licence

CC BY 4.0, matching the original notes.
