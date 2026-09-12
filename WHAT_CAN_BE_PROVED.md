# What this machinery can prove, what it can only predict, and why it cannot prove the twin prime conjecture by contradiction

Companion to [REFINED_CONJECTURES.md](REFINED_CONJECTURES.md).  Notation as
there: $\mathcal T$ = lower twin primes, $C_n=p_n+p_{n+1}+1$, $d(t)$ = least
productive gap.

## 1. Three tiers of statements

Everything in this repository falls into one of three tiers.  Keeping them
apart is the whole point of this document.

| tier | examples | status |
|---|---|---|
| **Proved, unconditional** | Lemmas 1–6 (residue classes, admissibility for every gap $g$ and every $t\ge11$, the absolute bound $S(t)\ge S_{\min}$, $t=3$ has no productive gap); Proposition 7 (logical relations); the Selberg-sieve **upper bounds** of §2; the theorems of [`paper/`](paper/bierton_local_constants.tex): explicit finite-product formula and sharp bounds for $R(g)$, the mean values $\frac6G\sum S_4\to24C_2^2$, $\frac6G\sum S_6\to24C_2^2\bar R$ with $\bar R$ and $\kappa$ as Euler products, the bound $N(X)\ll X/(\log X)^3$, and the identities bi-twin $=$ quadruplet, $S_6(6)=3\,S(\text{sextuplet})$ | theorems |
| **Proved, conditional** | Theorem A: Hypothesis H $\Rightarrow$ Conjecture A.  Theorem B: lower-bound uniform Bateman–Horn $\Rightarrow$ $d(t)\le t^\theta$ for *all* $t\ge t_1(\theta)$ | implications; the hypotheses are open |
| **Conjectured, tested** | A′ (asymptotic count with constant $\kappa$), B′ ($d(t)\le(\log t)^5\log\log t$, Poisson model), every table produced by `twinconj constellation` | agree with data to 0.1–3 % up to $10^{10}$, with 14,000 independent random twins of 20–150 digits, and along a proved 1,134-step orbit reaching 343 digits; not proved |

Nothing moves from the third tier to the first by computation, however far
it is pushed: all three original statements and all their refinements imply
the twin prime conjecture (Proposition 7), so proving any of them
unconditionally *is* proving the twin prime conjecture.

## 2. What is provable right now: upper bounds of the correct order

The one unconditional tool that reaches the counts in these conjectures is
the Selberg upper-bound sieve.  For any admissible tuple of $k$ distinct
linear forms with singular series $S$ (Halberstam–Richert, *Sieve Methods*,
Thm 5.7):

$$\#\{n\le X:\ \text{all }k\text{ forms prime}\}\ \le\ \bigl(2^k k!+o(1)\bigr)\,S\,\frac{X}{(\log X)^k}.$$

Applied to the tuples of the notes this gives, unconditionally,

* consecutive twin pairs at gap 6 (prime quadruplets): $\le(384+o(1))\,S_4(6)\,X/(\log X)^4$;
* propagating consecutive pairs at gap 6: $N_6(X)\le(46080+o(1))\,S_6(6)\,X/(\log X)^6$;
* for fixed $t$ and $Y\ge t^{\theta}$, productive gaps $d\le Y$ with $d-1$ prime: $\ll_\theta S^-(t)\,Y/(\log Y)^5$ (the sieve bound is uniform only when the coefficients are polynomial in the range, which is why $Y\ge t^\theta$ is needed — the same range as in Theorem B);
* total propagating pairs: $N(X)\le\pi_2(X)\le(16+o(1))\,C_2\,X/(\log X)^2$ (improvable to $6.8\,C_2$ by Wu's refinement of the twin-prime sieve bound) — and, non-trivially, $N(X)\ll X/(\log X)^3$ (`paper/`, Thm 1.5): split the consecutive pairs by gap, bound the pairs with gap $>(\log X)^3$ by $X/(\log X)^3$ since the gaps are disjoint intervals in $[1,X]$, and sum the sieve bound $\ll S_6(g)X/(\log X)^6$ over $g\le(\log X)^3$ using $\sum_{g\le G}S_6(g)\ll G$ (the mean-value theorem).  The remaining logarithm is exactly the missing knowledge about large gaps between twins.

These are the *right order of magnitude* in every case, with constants that
are $2^k k!$ times the conjectured ones.  `twinconj constellation` prints the
leading term of the bound next to the actual count and the Bateman–Horn
prediction:

| tuple ($n\le10^9$) | count | Bateman–Horn | Selberg bound (leading term) |
|---|---|---|---|
| $(n,n+2,n+6,n+8)$ | 28,388 | 28,387.0 | 8,643,111 |
| $(n,n+2,n+6,n+8,2n+7,2n+9)$ | 918 | 896.0 | 30,192,270 |
| $(n,n+2,2n+1,2n+3)$ | 26,370 | 26,455.7 | 8,643,111 |
| $(n,2n+1,4n+3)$ | 342,414 | 342,312.5 | 15,415,820 |
| $(n,2n+1)$ | 3,308,859 | 3,307,887.9 | 24,595,405 |

The gap between the second and third columns is the parity barrier made
visible: the conjecture is accurate to four digits, the theorem is off by a
factor $2^k k!$ *and* is one-sided.  No unconditional **lower** bound
exists for any of these counts, not even "$\ge1$ infinitely often".

## 3. What is close

Closest unconditional results in the literature, and what they do and do
not give here:

* **Chen (1973).** Infinitely many primes $p$ with $p+2$ a prime or a product
  of two primes.  The propagation analogue — infinitely many consecutive
  twins with $C_n$ prime and $C_n+2\in P_2$ — is *not* a consequence: Chen's
  argument sieves a single 2-tuple and cannot be run inside the 4-tuple
  condition "$n,n+2,n+g,n+g+2$ all prime", whose density is already below the
  sieve level.
* **Zhang / Maynard–Tao / Polymath (2013–14).** For any admissible set of
  50 linear forms $a_in+b_i$, infinitely many $n$ make at least two of them
  prime.  Taking 50 forms of pairwise distinct slopes yields infinitely many
  prime pairs $(p,q)$ with $a_jp-a_iq=a_jb_i-a_ib_j$ for *some* fixed
  $(i,j)$ — but the method never controls *which* two forms, so nothing can
  be said about a specific 4- or 6-tuple, and nothing about slope-1 pairs at
  distance 2.
* **Conditional resolutions (this repository).** Both conjectures are
  formal consequences of standard hypotheses, now with no exceptional sets
  and an absolute constant (Theorem B).  Under Hypothesis H, Conjecture A is
  a theorem; under lower-bound uniform Bateman–Horn, $d(t)\le t^\theta$ for
  every large $t$.  This is the strongest thing that *can* be said, and the
  original notes already said it in a slightly weaker form.

What the machinery does yield immediately is *more conjectures of the same
quality*.  The `constellation` command takes any tuple of linear forms and
returns count, Bateman–Horn prediction, and Selberg bound; presets include
the natural relatives of the two conjectures:

* `bi-twin`: lower twins $t$ with $2t+1\in\mathcal T$ — the degenerate
  ($q=p$) case of the propagation map.  **This is not new**: with
  $n=t+1$ the condition is $n\pm1,\ 2n\pm1$ all prime, the *bi-twin chain*
  of one link (OEIS A066388; iterating $t\mapsto2t+1$ gives the longer
  bi-twin chains searched by record hunters and used as Primecoin's
  proof-of-work since 2013; the quadruple also appears in Shevelev,
  arXiv:0911.5478).  Count to $10^9$: 26,370 vs 26,455.7 predicted, with
  $S=4.15118\ldots$, numerically the quadruplet constant.
  The useful observation is the *relation* to Bierton's map: with twin
  centres $m_n=p_n+1$, propagation says $m_n+m_{n+1}$ is a twin centre
  (since $C_n+1=p_n+p_{n+1}+2$), while a bi-twin link says $2m_n$ is a twin
  centre.  Propagation is the additive analogue of the known multiplicative
  construction; the additive version does not appear to be in the
  literature (quick search, not exhaustive).
* `cunningham-3`, `sophie-germain`: Sophie Germain chains, the classical
  analogue of the orbit $t\mapsto 2t+d+1$ with $d=0$.
* `propagation-12`: the gap-12 twin pairs whose $C$ is a lower twin (here
  consecutiveness is *not* automatic, so this counts a superset of the
  consecutive gap-12 propagating pairs of A′.3).

## 4. On proving the twin prime conjecture by contradiction

The request was: assume $\mathcal T$ is finite and derive a contradiction
from the framework.  Here is exactly what happens.

**Proposition 8.** Let $P=\max\mathcal T$ (assumed to exist).

1. Then Conjectures A, B, A′, B′ are all false: $N(X)$ is eventually
   constant, and $P$ has no productive gap (a productive gap would give
   $P+d\in\mathcal T$ with $P+d>P$).
2. Hence a contradiction is obtained **exactly** by proving one of A, B, A′,
   B′ — or any other statement $\Phi$ with $\Phi\Rightarrow$ "there is a
   lower twin $>P$".  Every such $\Phi$ implies the twin prime conjecture.
   In particular B is *strictly stronger*: it asserts not only infinitely
   many twins but a polylogarithmic search that finds the next one from the
   current one.  A proof by contradiction through B is a proof of B, a
   harder theorem than the one being sought.
3. The unconditional inputs available (Lemmas 1–6, the Selberg bounds) are
   all *local*: they say which residue classes the objects must lie in and
   how many of them there can be at most.  Local information is consistent
   with $\mathcal T$ being finite.  This is not a deficiency of these
   particular lemmas but Selberg's **parity phenomenon**: two sequences with
   identical residue-class statistics up to level $X^{1-\varepsilon}$ can
   have all their elements with an odd, respectively even, number of prime
   factors; a method using only that information cannot tell them apart,
   and therefore cannot show that a sieved set contains a single prime, let
   alone two primes at distance 2 (Friedlander–Iwaniec, *Opera de Cribro*,
   ch. 16).  The twin problem is the parity problem in its purest form,
   because the 2-tuple $(n,n+2)$ has no additional structure to exploit.
4. Consequently no chain of inferences built from the contents of this
   repository (or of the original three) terminates in a contradiction with
   "$\mathcal T$ is finite" without, at some step, *assuming* a statement of
   tier three.  Making that step explicit is what the certificate and the
   tier table above do.  $\square$

What a valid proof would need is an input of a genuinely different kind — a
bilinear ("Type II") estimate for the specific sequence, which is what broke
parity in the Friedlander–Iwaniec theorem on primes of the form $x^2+y^4$,
and which is not available for $(n,n+2)$: there is no second variable.  That
is the state of the art, and this repository does not change it.  It was not
possible to add a proof, and none has been added.

### A checklist for any future argument

If you write a contradiction argument, run each step through these three
questions; the step that fails one of them is where the circularity hides.

1. **Where does the new twin come from?**  The contradiction must exhibit or
   count a lower twin $>P$.  Name the step that produces it.
2. **Does that step use only residue-class data and upper bounds?**  If yes,
   it is blocked by parity (Proposition 8.3) and cannot be correct as
   stated.
3. **Is the statement being used at least as strong as the twin prime
   conjecture?**  If yes (A, B, A′, B′, Hypothesis H, Bateman–Horn all are),
   the argument is a proof of that statement and inherits its difficulty.

## 5. Reproduction

```bash
python -m twinconj constellation --list
python -m twinconj constellation --preset bi-twin --limit 1e9
python -m twinconj constellation --forms "n, n+2, 2n+1" --limit 1e8
```

Outputs for the five presets above are in `results/constellation_*_1e9.txt`.
