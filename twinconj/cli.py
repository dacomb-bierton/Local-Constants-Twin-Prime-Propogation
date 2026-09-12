"""Command line entry point: ``python -m twinconj <command>`` or ``twinconj``."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .local import (
    SingularSeries,
    TWIN_PRIME_CONSTANT,
    gap_series_lower_bound,
    propagation_mean_ratio_model,
    propagation_ratio,
    propagation_tuple,
    twin_pair_tuple,
    twin_prime_constant_numeric,
)
from .constellation import PRESETS as _PRESETS

PRESET_NAMES = tuple(_PRESETS)


def _num(s: str) -> int:
    return int(float(s))


def _emit(text: str, out: str | None) -> None:
    print(text)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text + "\n")
        print(f"\n[written to {out}]")


def cmd_certify(a: argparse.Namespace) -> int:
    from .certificate import render_all, run_all

    certs, ok = run_all(limit=a.limit, Q=a.Q)
    _emit(render_all(certs, ok), a.out)
    return 0 if ok else 1


def cmd_propagation(a: argparse.Namespace) -> int:
    from .propagation import format_report, run_propagation

    t0 = time.time()
    ss = SingularSeries(a.Q)
    res = run_propagation(a.limit, ss)
    text = format_report(res)
    text += f"\n\n  elapsed {time.time() - t0:.1f}s"
    _emit(text, a.out)
    return 0


def cmd_gaps(a: argparse.Namespace) -> int:
    from .gaps import attach_model, format_report, minimal_productive_gaps

    t0 = time.time()
    res = minimal_productive_gaps(a.limit, cap=a.cap)
    if a.model:
        attach_model(res, SingularSeries(a.Q), samples_per_block=a.samples)
    text = format_report(res) + f"\n\n  elapsed {time.time() - t0:.1f}s"
    _emit(text, a.out)
    return 0 if not res.missing else 1


def cmd_constants(a: argparse.Namespace) -> int:
    ss = SingularSeries(a.Q)
    L = []
    L.append(f"twin prime constant C_2 : exact {TWIN_PRIME_CONSTANT:.12f}, truncated product {twin_prime_constant_numeric(a.Q):.12f}")
    L.append(f"S(n, n+2) via machinery : {ss.value(((1, 0), (1, 2))):.12f}  (should be 2*C_2 = {2 * TWIN_PRIME_CONSTANT:.12f})")
    L.append(f"S_4(6) prime quadruplets: {ss.value(twin_pair_tuple(6)):.8f}")
    L.append(f"S_6(6) propagating gap 6: {ss.value(propagation_tuple(6)):.8f}")
    L.append("")
    L.append("  g      S_4(g)      S_6(g)       R(g)=S_6/S_4")
    for g in range(6, a.gmax + 1, 6):
        L.append(f"{g:4d}  {ss.value(twin_pair_tuple(g)):10.5f}  {ss.value(propagation_tuple(g)):10.5f}  {propagation_ratio(g, ss):10.5f}")
    L.append("")
    er = propagation_mean_ratio_model()
    L.append(f"model limit of mean R(g_n) over consecutive twin pairs: {er:.5f}")
    L.append(f"kappa_model = 2*C_2*E[R] = {2 * TWIN_PRIME_CONSTANT * er:.5f}   (N(X) ~ kappa * int dt/((ln t)^2 (ln 2t)^2))")
    L.append("")
    b = gap_series_lower_bound(a.Q)
    L.append("uniform lower bound for the gap 5-tuple singular series (t in T, t >= 11):")
    for k, v in b.items():
        L.append(f"  {k:18s} {v}")
    _emit("\n".join(L), a.out)
    return 0


def cmd_theorems(a: argparse.Namespace) -> int:
    from .theorems import format_report

    _emit(format_report(SingularSeries(a.Q), Q=a.Q), a.out)
    return 0


def cmd_verify_chain(a: argparse.Namespace) -> int:
    from .verify import attach_model, format_chain_verification, verify_chain_csv

    rows = verify_chain_csv(a.csv, check_minimal=not a.no_minimal)
    if not a.no_model:
        attach_model(rows, SingularSeries(a.Q))
    _emit(format_chain_verification(a.csv, rows), a.out)
    return 0 if all(r.ok for r in rows) else 1


def cmd_chain(a: argparse.Namespace) -> int:
    from .chain import build_chain, format_chain

    chain = build_chain(a.start, a.steps)
    _emit(format_chain(chain), a.out)
    return 0


def cmd_constellation(a: argparse.Namespace) -> int:
    from .constellation import PRESETS, format_report, forms_to_str, parse_forms, run_constellation

    if a.list:
        for name, (spec, desc) in PRESETS.items():
            print(f"  {name:16s} {spec:34s} {desc}")
        return 0
    if a.preset:
        spec, desc = PRESETS[a.preset]
    elif a.forms:
        spec, desc = a.forms, None
    else:
        raise SystemExit("give --preset NAME or --forms 'n, n+2, ...' (or --list)")
    t0 = time.time()
    forms = parse_forms(spec)
    res = run_constellation(forms, a.limit, SingularSeries(a.Q))
    text = format_report(res, desc) + f"\n\n  elapsed {time.time() - t0:.1f}s"
    _emit(text, a.out)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="twinconj", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("certify", help="machine-check the lemmas")
    s.add_argument("--limit", type=_num, default=200_000)
    s.add_argument("--Q", type=_num, default=1_000_000)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_certify)

    s = sub.add_parser("propagation", help="Conjecture A': actual vs predicted propagating pairs")
    s.add_argument("--limit", type=_num, default=10_000_000)
    s.add_argument("--Q", type=_num, default=1_000_000)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_propagation)

    s = sub.add_parser("gaps", help="Conjecture B': minimal productive gaps d(t)")
    s.add_argument("--limit", type=_num, default=1_000_000)
    s.add_argument("--cap", type=_num, default=1 << 25)
    s.add_argument("--model", action="store_true", help="also evaluate the Bateman-Horn model mean")
    s.add_argument("--samples", type=int, default=150)
    s.add_argument("--Q", type=_num, default=1_000_000)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_gaps)

    s = sub.add_parser("constants", help="singular series and R(g) table")
    s.add_argument("--Q", type=_num, default=1_000_000)
    s.add_argument("--gmax", type=int, default=120)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_constants)

    s = sub.add_parser("theorems", help="closed-form constants: R_inf, R_min, Rbar, kappa, identities")
    s.add_argument("--Q", type=_num, default=10_000_000)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_theorems)

    s = sub.add_parser("verify-chain", help="re-check an orbit CSV (step,t,d,C,...) produced by another program")
    s.add_argument("csv")
    s.add_argument("--no-minimal", action="store_true", help="skip the (slow) check that d is the least productive gap")
    s.add_argument("--no-model", action="store_true", help="skip the Poisson-model columns E[d(t)] and P(d(t) > d)")
    s.add_argument("--Q", type=_num, default=1_000_000)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_verify_chain)

    s = sub.add_parser("chain", help="constructive orbit t -> 2t + d(t) + 1")
    s.add_argument("--start", type=int, default=5)
    s.add_argument("--steps", type=int, default=40)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_chain)

    s = sub.add_parser("constellation", help="any tuple of linear forms: count vs Bateman-Horn vs Selberg bound")
    s.add_argument("--preset", choices=sorted(PRESET_NAMES))
    s.add_argument("--forms", help="e.g. 'n, n+2, 2n+1'")
    s.add_argument("--list", action="store_true", help="list presets")
    s.add_argument("--limit", type=_num, default=10_000_000)
    s.add_argument("--Q", type=_num, default=1_000_000)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_constellation)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
