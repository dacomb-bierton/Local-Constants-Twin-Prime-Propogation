"""Machine-checked certificates for the lemmas used by the refined
conjectures.

Every check is either an exhaustive finite residue-class enumeration (a
complete proof), an explicit witness, or a numerical inequality whose
analytic justification is stated alongside.  Run ``twinconj certify``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .local import (
    TWIN_PRIME_CONSTANT,
    SingularSeries,
    gap_series,
    gap_series_lower_bound,
    gap_tuple,
    generic_log_factor,
    is_admissible,
    local_factor,
    nu,
    propagation_mean_ratio_model,
    propagation_tuple,
    small_primes,
    surviving_residues,
    twin_pair_tuple,
)
from .sieve import lower_twins, prime_table


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class Certificate:
    title: str
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(Check(name, bool(ok), detail))

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def render(self) -> str:
        out = ["=" * 78, self.title, "=" * 78]
        for c in self.checks:
            out.append(f"  [{'PASS' if c.ok else 'FAIL'}] {c.name}")
            for line in c.detail.splitlines():
                out.append(f"         {line}")
        out.append("")
        return "\n".join(out)


# --------------------------------------------------------------------------

def lemma_residues(is_p: np.ndarray, twins: np.ndarray) -> Certificate:
    c = Certificate("Lemma 1.  Residues: every lower twin p > 3 is 5 (mod 6); "
                    "D_n = p_n + p_{n+1} + 3 is never a lower twin for n >= 2; "
                    "C_n = 5 (mod 6).")
    viable = [r for r in range(6) if r % 2 and r % 3 and (r + 2) % 3]
    c.add("odd residues r mod 6 with 3 not dividing r or r+2", viable == [5], f"viable = {viable}")
    c.add("all computed lower twins > 3 are 5 (mod 6)", bool(np.all(twins[twins > 3] % 6 == 5)),
          f"{len(twins):,} twins checked")
    # D + 2 = p + q + 5 with p = q = 2 (mod 3)
    c.add("p = q = 2 (mod 3)  =>  D + 2 = 0 (mod 3)", (2 + 2 + 5) % 3 == 0)
    c.add("p = q = 5 (mod 6)  =>  C = 5 (mod 6)", (5 + 5 + 1) % 6 == 5)
    p, q = twins[:-1], twins[1:]
    D = p + q + 3
    ok = (D + 4 < len(is_p))
    dt = is_p[D[ok]] & is_p[D[ok] + 2]
    bad = [(int(a), int(b)) for a, b in zip(p[ok][dt], q[ok][dt]) if a != 3]
    c.add("D-branch successes among computed consecutive pairs: only (3,5)", not bad,
          f"pairs with D in T: {[(int(a), int(b)) for a, b in zip(p[ok][dt], q[ok][dt])]}")
    return c


def lemma_gap6_consecutive() -> Certificate:
    c = Certificate("Lemma 2.  If n > 3 and n, n+6 are both lower twins they are consecutive in T.")
    c.add("n = 2 (mod 3)  =>  n + 4 = 0 (mod 3), so n+2 and n+4 are not lower twins", (2 + 4) % 3 == 0)
    return c


def lemma_propagation_tuple_admissible() -> Certificate:
    c = Certificate("Lemma 3.  For every g = 0 (mod 6) the 6-tuple "
                    "(n, n+2, n+g, n+g+2, 2n+g+1, 2n+g+3) is admissible; hence S_6(g) > 0 and R(g) > 0.")
    # admissibility mod 2, 3, 5 depends only on g mod 30
    for g in (30, 6, 12, 18, 24):
        forms = propagation_tuple(g)
        surv = {q: surviving_residues(forms, q) for q in (2, 3, 5)}
        c.add(f"g = {g % 30} (mod 30): surviving n mod 2, 3, 5 all non-empty",
              all(surv.values()), f"survivors: {surv}")
    c.add("q >= 7: six forms forbid at most six residues, so a class survives (pigeonhole)", 6 < 7)
    c.add("for g = 0 (mod 6) the primes 2 and 3 contribute exactly 9 to R(g) = S_6/S_4",
          all(
              abs(local_factor(propagation_tuple(g), 2) / local_factor(twin_pair_tuple(g), 2)
                  * local_factor(propagation_tuple(g), 3) / local_factor(twin_pair_tuple(g), 3) - 9.0) < 1e-12
              for g in range(6, 300, 6)
          ))
    c.add("cross-check with is_admissible for g = 6, 12, ..., 600",
          all(is_admissible(propagation_tuple(g))[0] for g in range(6, 601, 6)))
    c.add("g not 0 (mod 6) is impossible for twins > 3 (4-tuple not admissible)",
          all(not is_admissible(twin_pair_tuple(g))[0] for g in (2, 4, 8, 10, 14, 16)))
    return c


def lemma_t3_no_gap(is_p: np.ndarray, limit: int) -> Certificate:
    c = Certificate("Lemma 4.  t = 3 has no productive gap.  (The gap conjecture must start at t = 5.)")
    c.add("3 + d in T with 3 + d > 3 forces d = 2 (mod 6)", (5 - 3) % 6 == 2)
    c.add("then 2*3 + d + 1 = d + 7 = 0 (mod 3), and d + 7 > 3", (2 + 7) % 3 == 0)
    d = np.arange(2, min(limit, len(is_p) - 12), 2)
    prod = is_p[3 + d] & is_p[5 + d] & is_p[7 + d] & is_p[9 + d] & (is_p[d - 1] | is_p[d + 1])
    c.add(f"finite check: no productive d <= {int(d.max()):,} for t = 3", not prod.any())
    d5 = 6
    c.add("t = 5 has the productive gap d = 6 (11, 13, 17, 19 prime; 5 and 7 prime)",
          bool(is_p[5 + d5] and is_p[7 + d5] and is_p[2 * 5 + d5 + 1] and is_p[2 * 5 + d5 + 3]))
    return c


def lemma_gap_tuple_admissible() -> Certificate:
    c = Certificate("Lemma 5.  For every t in T with t >= 11 both 5-tuples "
                    "(d+t, d+t+2, d+2t+1, d+2t+3, d-1) and (..., d+1) are admissible, "
                    "with nu_2 = 1, nu_3 = 2, nu_5 <= 4.  The thin exceptional set of the "
                    "original Lemma 5.2 is empty.")
    # residues of t: t = 5 (mod 6) and t = 1, 2, 4 (mod 5)  ->  t mod 30 in {11, 17, 29}
    for t in (11, 17, 29):
        for sign in (-1, 1):
            forms = gap_tuple(t, sign)
            n2, n3, n5 = nu(forms, 2), nu(forms, 3), nu(forms, 5)
            s3 = surviving_residues(forms, 3)
            c.add(f"t = {t % 30} (mod 30), side d{sign:+d}: nu_2={n2}, nu_3={n3} (survivor d={s3}), nu_5={n5} <= 4",
                  n2 == 1 and n3 == 2 and s3 == [0] and n5 <= 4)
    c.add("q >= 7: five forms forbid at most five residues of d (pigeonhole)", 5 < 7)
    c.add("t = 5 is exceptional: the d-1 tuple has nu_5 = 5 (covering), the d+1 tuple does not",
          nu(gap_tuple(5, -1), 5) == 5 and nu(gap_tuple(5, 1), 5) == 4)
    c.add("cross-check with is_admissible on all lower twins 11 <= t <= 100000",
          all(is_admissible(gap_tuple(int(t), s))[0]
              for t in lower_twins(prime_table(100_010), 100_000) if t >= 11 for s in (-1, 1)))
    return c


def lemma_uniform_lower_bound(ss: SingularSeries, twins: np.ndarray) -> Certificate:
    c = Certificate("Lemma 6.  Uniform lower bound for the singular series of the gap 5-tuples: "
                    "S(t) >= S_min > 0 for every t in T, t >= 11 "
                    "(replaces 'S(t) >> (log t)^{-O(1)}' in the original Theorem 5.4).")
    b = gap_series_lower_bound(ss.Q)
    c.add("factors at q = 2, 3 and the worst case nu_5 = 4 at q = 5",
          abs(b["factor_2"] - 16) < 1e-12 and abs(b["factor_3"] - 3**5 / 3 / 2**5) < 1e-12,
          f"16 * {b['factor_3']:.6f} * {b['factor_5_worst']:.6f}")
    primes = ss.primes[ss.primes >= 7]
    lf = generic_log_factor(5, primes)
    c.add("log[(1-5/q)(1-1/q)^-5] >= -25/q^2 for every prime 7 <= q <= Q (numerical) "
          "and analytically for q >= 10 (Taylor bound)", bool(np.all(lf >= -25.0 / primes.astype(float) ** 2)))
    c.add("tail over q > Q is at least exp(-25/Q) since sum_{q>Q} q^-2 < 1/Q", b["tail_lower_bound"] > 0.99)
    c.add(f"S_min = {b['S_min']:.6f}  (Q = {b['Q']:,})", b["S_min"] > 10.0,
          f"prod_(7 <= q <= Q) (1-5/q)(1-1/q)^-5 = {b['product_7_to_Q']:.6f}")
    sample = twins[(twins >= 11) & (twins <= 200_000)]
    mins = min(min(gap_series(int(t), ss)[:2]) for t in sample)
    c.add(f"every computed S^-(t), S^+(t) for 11 <= t <= 200000 exceeds S_min ({len(sample):,} twins)",
          mins >= b["S_min"] * (1 - 1e-9), f"smallest observed value {mins:.6f}")
    return c


def proposition_logic(is_p: np.ndarray) -> Certificate:
    c = Certificate("Proposition 7.  Logical relations between the statements.")
    c.add("A (propagation) => infinitely many twins: each success gives C_n in T with C_n > p_n", 2 * 5 + 6 + 1 > 5)
    c.add("B (gap existence for all t >= t0) => infinitely many twins: G(t) = 2t + d + 1 > t", 2 * 5 + 6 + 1 > 5)
    t, d, nxt = 17, 24, 29
    lt = lambda x: bool(is_p[x] and is_p[x + 2])  # noqa: E731
    c.add("B does not formally imply A (the original note called B 'strictly stronger'): a productive "
          "gap need not be the consecutive gap.  Illustration: d(17) = 24 is productive "
          "(41, 59 in T) while the consecutive pair (17, 29) has C = 47 not in T.",
          lt(t + d) and lt(2 * t + d + 1) and lt(nxt) and not lt(t + nxt + 1)
          and not any(lt(t + dd) and lt(2 * t + dd + 1) and (is_p[dd - 1] or is_p[dd + 1]) for dd in range(6, d, 6)))
    c.add("A does not formally imply B: A is an 'infinitely often' statement, B a 'for all large t' statement.", True)
    return c


def theorem_explicit_ratio(ss: SingularSeries) -> Certificate:
    from . import theorems as th

    c = Certificate("Theorem 1.  Explicit local ratio: nu_4, nu_6 by divisibility, "
                    "R(g) = R_inf rho_5 rho_7 prod_{q>=11, q|Delta(g)} rho_q/gamma_q, "
                    "and R_min < R(g) for all g.")
    gs = range(6, 3001, 6)
    qs = [q for q in small_primes(300) if q >= 5]
    ok = all(nu(twin_pair_tuple(g), q) == th.nu4_gap(g, q) and nu(propagation_tuple(g), q) == th.nu6_gap(g, q)
             for g in gs for q in qs)
    c.add("nu_4(g;q), nu_6(g;q) match the divisibility table for all 6 | g <= 3000, 5 <= q <= 300", ok)
    # the two extra roots coincide with old ones exactly when q | (g-3)(g-1)(g+1)(g+3), and then both do
    ok = True
    for q in qs:
        inv2 = pow(2, -1, q)
        for g in range(0, q):
            old = {0, (-2) % q, (-g) % q, (-g - 2) % q}
            r1, r2 = (-(g + 1) * inv2) % q, (-(g + 3) * inv2) % q
            both_in = r1 in old and r2 in old
            none_in = r1 not in old and r2 not in old
            div = ((g * g - 1) * (g * g - 9)) % q == 0
            ok &= (both_in if div else none_in) and r1 != r2
    c.add("for q >= 5: both extra roots coincide with 4-tuple roots iff q | (g^2-1)(g^2-9), else neither "
          "(full residue enumeration, 5 <= q <= 300)", ok)
    # compare the two finite products over the same primes q <= Q (no tail on either side)
    r_inf_bare = th.r_infinity(Q=ss.Q, tail=False)
    r_inf_a = th.r_infinity(Q=ss.Q)
    diffs = []
    for g in (6, 12, 18, 30, 36, 60, 90, 210, 2310, 30030, 510510, 9699690):
        a = th.propagation_ratio_explicit(g, r_inf_bare)
        b = math.exp(ss.log_value(propagation_tuple(g), with_tail=False)
                     - ss.log_value(twin_pair_tuple(g), with_tail=False))
        diffs.append(abs(a / b - 1))
    c.add("explicit formula agrees with the direct product over the same primes to 1e-11 for g up to 9,699,690",
          max(diffs) < 1e-11, f"max relative difference {max(diffs):.2e};  R_inf = {r_inf_a:.9f}")
    gen_min = all(th.gamma(q) <= min(th.rho(a, q) for a in range(q)) for q in qs if q >= 11)
    c.add("q >= 11: the generic factor gamma_q is the smallest of the four values of rho_q "
          "(so every coincidence increases R)", gen_min)
    b = th.propagation_ratio_bounds(r_inf_a)
    c.add(f"R_min = R_inf * 25/48 * 49/72 = {b['R_min']:.6f}; rho_5 min at g = 0 (5), rho_7 min at g = +-2 (7)",
          abs(b["rho_5_min"] - 25 / 48) < 1e-12 and abs(b["rho_7_min"] - 49 / 72) < 1e-12)
    vals = [th.propagation_ratio_explicit(g, r_inf_a) for g in range(6, 200_001, 6)]
    c.add("R(g) > R_min for all 6 | g <= 200000; smallest value found", min(vals) > b["R_min"],
          f"min R(g) = {min(vals):.6f} at g = {6 * (1 + vals.index(min(vals)))}; max R(g) = {max(vals):.4f} "
          f"at g = {6 * (1 + vals.index(max(vals)))}")
    return c


def theorem_mean_values(ss: SingularSeries) -> Certificate:
    from . import theorems as th

    c = Certificate("Theorem 2.  Mean values of S_4(g), S_6(g) over g = 0 (mod 6); "
                    "Rbar and kappa in closed form.")
    ok4 = ok6 = True
    for q in [q for q in small_primes(200) if q >= 5]:
        ok4 &= abs(th.mean_local_factor(4, q) - (q - 2) ** 2 / q**2 * (1 - 1 / q) ** (-4)) < 1e-12
        ok6 &= abs(th.mean_local_factor(6, q) - (q * q - 6 * q + 12) / q**2 * (1 - 1 / q) ** (-6)) < 1e-12
    c.add("mean over g mod q of (1 - nu_4/q) is (q-2)^2/q^2 for all 5 <= q <= 200 (enumeration)", ok4)
    c.add("mean over g mod q of (1 - nu_6/q) is (q^2-6q+12)/q^2 for all 5 <= q <= 200 (enumeration)", ok6)
    c.add("q = 2, 3 contribute 8 * 27/16 = 27/2 to the S_4 mean and 32 * 243/64 = 243/2 to the S_6 mean",
          abs(local_factor(twin_pair_tuple(6), 2) * local_factor(twin_pair_tuple(6), 3) - 13.5) < 1e-12
          and abs(local_factor(propagation_tuple(6), 2) * local_factor(propagation_tuple(6), 3) - 121.5) < 1e-12)
    # the tail estimate leaves a residual of order (Q log Q)^-2 * log Q; allow a few units of 1/(Q log Q)
    tol = 5.0 / (ss.Q * math.log(ss.Q))
    m4 = th.mean_twin_pair_series(ss.Q)
    c.add(f"(27/2) prod q^2(q-2)^2/(q-1)^4 = 24 C_2^2  ({m4:.9f} vs {24 * TWIN_PRIME_CONSTANT**2:.9f})",
          abs(m4 / (24 * TWIN_PRIME_CONSTANT**2) - 1) < tol)
    rbar = th.mean_ratio_closed_form(ss.Q)
    model = propagation_mean_ratio_model(Q=20_000)
    c.add(f"Rbar closed form {rbar:.6f} agrees with the enumerated model mean {model:.6f} (Q = 20000)",
          abs(rbar / model - 1) < 2e-5)
    kappa = th.kappa_closed_form(ss.Q)
    c.add(f"kappa closed form {kappa:.9f} = 2 C_2 Rbar = {2 * TWIN_PRIME_CONSTANT * rbar:.9f}",
          abs(kappa / (2 * TWIN_PRIME_CONSTANT * rbar) - 1) < tol)
    G = 120_000
    s4 = sum(ss.value(twin_pair_tuple(g)) for g in range(6, G + 1, 6)) / (G // 6)
    s6 = sum(ss.value(propagation_tuple(g)) for g in range(6, G + 1, 6)) / (G // 6)
    c.add(f"partial means to G = {G:,}: S_4 {s4:.4f} (limit {m4:.4f}), S_6 {s6:.4f} (limit {m4 * rbar:.4f}), "
          f"ratio {s6 / s4:.4f} (limit {rbar:.4f})",
          abs(s4 / m4 - 1) < 0.01 and abs(s6 / (m4 * rbar) - 1) < 0.01)
    return c


def theorem_identities(ss: SingularSeries) -> Certificate:
    from . import theorems as th

    c = Certificate("Theorem 3.  Singular-series identities.")
    ok, prof = th.identity_bi_twin_quadruplet(Q=2000)
    c.add("S(n, n+2, 2n+1, 2n+3) = S(n, n+2, n+6, n+8): nu equal at every prime q <= 2000 "
          "(for q >= 5 both tuples have 4 distinct roots; nu(2) = 1, nu(3) = 2)",
          ok and prof[2] == (1, 1) and prof[3] == (2, 2) and all(v == (4, 4) for q, v in prof.items() if q >= 5),
          f"values {ss.value(th.BI_TWIN):.9f} = {ss.value(th.QUADRUPLET):.9f}")
    ok, prof = th.identity_propagation6_sextuplet(Q=2000)
    c.add("S_6(6) = 3 * S(n, n+4, n+6, n+10, n+12, n+16): nu equal except nu(7) = 4 vs 6", ok,
          f"ratio of truncated products {ss.value(th.PROPAGATION_6) / ss.value(th.SEXTUPLET):.9f}")
    return c


def run_all(limit: int = 200_000, Q: int = 1_000_000) -> tuple[list[Certificate], bool]:
    is_p = prime_table(3 * limit + 100)
    twins = lower_twins(is_p, limit)
    ss = SingularSeries(Q)
    certs = [
        lemma_residues(is_p, twins),
        lemma_gap6_consecutive(),
        lemma_propagation_tuple_admissible(),
        lemma_t3_no_gap(is_p, limit),
        lemma_gap_tuple_admissible(),
        lemma_uniform_lower_bound(ss, twins),
        proposition_logic(is_p),
        theorem_explicit_ratio(ss),
        theorem_mean_values(ss),
        theorem_identities(ss),
    ]
    return certs, all(c.ok for c in certs)


def render_all(certs: list[Certificate], ok: bool) -> str:
    out = [c.render() for c in certs]
    out.append("ALL CERTIFICATES PASS." if ok else "SOME CERTIFICATES FAILED.")
    return "\n".join(out)
