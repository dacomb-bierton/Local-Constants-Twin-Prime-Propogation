# Refined Twin-Prime Conjectures

Sharpened, quantitative and effective versions of the three statements in
Dacomb Bierton's notes

* *A Twin-Prime Propagation Conjecture* (repo `TwinPrimePropogation`),
* *A Twin-Gap Existence Conjecture* (repo `A-Twin-Gap-Existence-Conjecture`),
* *Structural Reduction of Two Twin-Prime Conjectures and Conditional
  Resolution under Hypothesis H* (repo `Structural-Reduction-...`),

together with the computations that support them.  Everything numerical in
this document is reproduced by the `twinconj` package in this repository
(see [README.md](README.md)); the finite lemmas are machine-checked by
`python -m twinconj certify`.

## Summary of what changed

| | Original statement | Refined statement |
|---|---|---|
| **A** Propagation | Infinitely many consecutive lower twins $(p_n,p_{n+1})$ with $C_n$ or $D_n\in\mathcal T$. | **A′.** $N(X)=\#\{n: p_n\le X,\ C_n\in\mathcal T\}$ satisfies $N(X)\sim\sum_{p_n\le X} R(g_n)/\log C_n\log(C_n+2)$ with an explicit local factor $R(g)$; equivalently $N(X)\sim\kappa\int_5^X \frac{dt}{(\log t)^2(\log 2t)^2}$, $\kappa=2C_2\bar R=14.76768\ldots$ (closed form below). Gap-resolved version and an exact Bateman–Horn form for gap 6. The $D_n$ branch is dropped (it contributes only $(3,5)$). |
| **B** Gap existence | Every sufficiently large $t\in\mathcal T$ has a productive gap $d=o(t)$. | **B′.** Every $t\in\mathcal T$ with $t\ge 5$ has a productive gap, and the least one satisfies $d(t)\le(\log t)^5\log\log t$. Typical size $\asymp(\log t)^4\log\log t$ (block means $\approx 0.0575\,(\log t)^4\log\log t$); the distribution of $d(t)$ follows an explicit Poisson model. $t=3$ has **no** productive gap, so "sufficiently large" means $t\ge5$. |
| **C** Reduction | A $\Leftarrow$ Hypothesis H for one 6-tuple. B $\Leftarrow$ uniform Bateman–Horn ($Y\ge X^\theta$) *outside a thin set of $t$*, with $S(t)\gg(\log t)^{-O(1)}$. B called "strictly stronger" than A. | **C′.** The exceptional set is empty: for **every** $t\in\mathcal T$, $t\ge11$, both 5-tuples are admissible and $S(t)\ge S_{\min}=10.1315\ldots$ uniformly. Hence only a *lower-bound* uniform Bateman–Horn hypothesis is needed and the conclusion $d(t)\le t^{\theta}$ holds for all $t\ge t_0(\theta)$ without exceptions. Hypothesis H gives infinitely many propagating pairs for the gap-6 tuple; the analogous 6-tuple is admissible for every gap $g\equiv0\pmod 6$. Correction: A and B are formally **incomparable**, not ordered. |

**Unconditional theorems (new; full proofs in
[`paper/bierton_local_constants.tex`](paper/bierton_local_constants.tex),
PDF alongside).**  The constants of A′ are now *exact*, not modelled:

1. *Explicit local ratio.* $R(g)=R_\infty\,\rho_5(g)\rho_7(g)\prod_{q\ge11,\,q\mid\Delta(g)}\rho_q(g)/\gamma_q$ with $R_\infty=5.87823926\ldots$ and $\Delta(g)=g(g^2-1)(g^2-4)(g^2-9)$; sharp bounds $2.08357729\ldots<R(g)\ll(\log\log g)^2$.
2. *Mean values.* $\frac6G\sum_{6\mid g\le G}S_4(g)\to24C_2^2$ and $\frac6G\sum_{6\mid g\le G}S_6(g)\to24C_2^2\bar R$ with $\bar R=9\prod_{q\ge5}\frac{q^2(q^2-6q+12)}{(q-1)^2(q-2)^2}=11.18489648\ldots$; hence $\kappa=2C_2\bar R=14.76768314\ldots$ in closed form.
3. *Upper bound.* $\#\{n:\ p_{n+1}\le X,\ C_n\in\mathcal T\}\ll X/(\log X)^3$ unconditionally (Selberg sieve + item 2), one logarithm short of the conjectured order.
4. *Identities.* $S(n,n+2,2n+1,2n+3)=S(n,n+2,n+6,n+8)$ (bi-twin chains ↔ prime quadruplets) and $S_6(6)=3\,S(\text{prime sextuplet})$.
5. *Exceptional origins.* The productive-gap 4-tuple is admissible for every $t\in\mathcal T$ except $t=3$; with the side condition "$d-1$ prime" the exceptions are exactly $\{3,5\}$ and $t=5$ has the unique gap $d=6$; with "$d+1$ prime" only $t=3$.

Everything in 1–5 is checked by `python -m twinconj certify` (Theorems 1–3 blocks) and printed by `python -m twinconj theorems`.

---

## 1. Notation and basic lemmas

$\mathcal T=\{3,5,11,17,29,41,59,71,101,\dots\}$ is the set of lower twin
primes, $p_n$ its $n$-th element, $g_n=p_{n+1}-p_n$, and

$$C_n=p_n+p_{n+1}+1=2p_n+g_n+1,\qquad D_n=C_n+2 .$$

An even $d>0$ is a *productive gap* for $t\in\mathcal T$ if
(i) $t+d\in\mathcal T$, (ii) $2t+d+1\in\mathcal T$, (iii) $d-1$ or $d+1$ is
prime.  $d(t)$ denotes the least productive gap of $t$.

**Lemma 1** (residues; original Lemmas 2.1–2.2). Every $p\in\mathcal T$ with
$p>3$ is $\equiv5\pmod 6$.  For $n\ge2$: $D_n\notin\mathcal T$ (because
$D_n+2\equiv0\pmod 3$), $C_n\equiv5\pmod 6$, and $g_n\equiv0\pmod 6$.  So for
$n\ge2$ the pair propagates iff $C_n$ and $C_n+2$ are both prime.

**Lemma 2** (gap 6 is consecutive; original Lemma 4.3). If $n>3$ and
$n,n+6\in\mathcal T$ then $n+4\equiv0\pmod3$, so no lower twin lies strictly
between them.

**Lemma 3** (new). For every $g\equiv0\pmod6$ the six linear forms

$$n,\ n+2,\ n+g,\ n+g+2,\ 2n+g+1,\ 2n+g+3$$

are admissible.  *Proof.* Mod 2 take $n$ odd; mod 3 take $n\equiv2$; mod 5
the answer depends only on $g\bmod5$ and each of the five classes has a
surviving residue (listed by the certificate); for $q\ge7$ six forms forbid
at most six of $q>6$ residues.  $\square$
Consequently $S_6(g)>0$ and the ratio $R(g)$ below is positive for every
admissible gap.

**Lemma 4** (new). $t=3$ has no productive gap.  *Proof.* $3+d\in\mathcal T$
with $3+d>3$ forces $d\equiv2\pmod 6$, and then
$2\cdot3+d+1=d+7\equiv0\pmod3$ with $d+7>3$.  $\square$
For $t>3$ every productive gap is $\equiv0\pmod6$, and $t=5$ has $d(5)=6$.

**Lemma 5** (new; replaces original Lemma 5.2). Let $t\in\mathcal T$,
$t\ge11$.  Both 5-tuples in the variable $d$,

$$d+t,\ d+t+2,\ d+2t+1,\ d+2t+3,\ d\mp1 ,$$

are admissible, with $\nu_2=1$, $\nu_3=2$ (only $d\equiv0\pmod 3$ survives)
and $\nu_5\le4$.  *Proof.* Mod 2 and 3 as in the original Lemma 5.1.  Mod 5 a
lower twin $t>5$ lies in one of the classes $t\equiv1,2,4$; the forbidden
residues of $d$ are $\{-t,-t-2,-2t-1,-2t-3,\pm1\}$ and a direct enumeration
gives $\nu_5=4,3,2$ (sign $-$) and $3,4,2$ (sign $+$) respectively — never 5.
For $q\ge7$ pigeonhole.  $\square$
(For $t=5$ the "$d-1$" tuple *is* covered mod 5; the "$d+1$" tuple is
admissible.  This is the only exception, and it is why the original note
needed a "thin set" — that set is $\{5\}$.)

**Lemma 6** (new; uniform lower bound). For every $t\in\mathcal T$, $t\ge11$,
and either sign, the singular series
$S(t)=\prod_q(1-\nu_q/q)(1-1/q)^{-5}$ satisfies

$$S(t)\ \ge\ S_{\min}\ =\ 16\cdot\tfrac{81}{32}\cdot\tfrac{5^4}{4^5}\cdot\prod_{q\ge7}\Bigl(1-\tfrac5q\Bigr)\Bigl(1-\tfrac1q\Bigr)^{-5}\ =\ 10.1315\ldots$$

*Proof.* The factors at 2, 3 are exact by Lemma 5, the factor at 5 is
minimised by $\nu_5=4$, and for $q\ge7$, $\nu_q\le5<q$ so each factor is at
least the generic one.  The generic product converges since
$\log[(1-5/q)(1-1/q)^{-5}]=-10/q^2+O(q^{-3})\ge-25/q^2$ for $q\ge7$, and
$\sum_{q>Q}q^{-2}<1/Q$ bounds the tail by $e^{-25/Q}$.  $\square$
The certificate evaluates the product to $Q=10^6$ and checks
$S(t)\ge S_{\min}$ on every twin $11\le t\le2\cdot10^5$ (the minimum
observed, $10.1346$ at $t=185{,}531$, is within $3\cdot10^{-4}$ of the bound,
so the bound is essentially sharp).

**Proposition 7** (logic). A $\Rightarrow$ infinitely many twins;
B $\Rightarrow$ infinitely many twins (orbit $t\mapsto2t+d(t)+1$).
Neither of A, B formally implies the other: A is an "infinitely often"
statement about *consecutive* gaps, B a "for all large $t$" statement about
*some* gap.  The original note's Claim 4 ("B is strictly stronger than A") is
therefore withdrawn; the example it gives ($t=17$ has no productive gap of
size 6) shows only that the gap-6 specialisation of B fails, not an
implication between A and B.  Illustration: $d(17)=24$ is productive
($41,59\in\mathcal T$) while the consecutive pair $(17,29)$ does not
propagate ($C=47$, $49=7^2$).

---

## 2. Conjecture A′ — quantitative propagation

### 2.1 Local factor

For $g\equiv0\pmod6$ let $S_4(g)$, $S_6(g)$ be the singular series of the
4-tuple $(n,n+2,n+g,n+g+2)$ and of the 6-tuple of Lemma 3, and put

$$R(g)=\frac{S_6(g)}{S_4(g)}=9\prod_{q\ge5}\frac{1-\nu_6(g,q)/q}{1-\nu_4(g,q)/q}\Bigl(1-\frac1q\Bigr)^{-2}.$$

$R(g)$ is the local correction to the probability that, *given* that $n$
and $n+g$ are lower twins, $2n+g+1$ is also a lower twin.  It varies a lot
with $g$:

| $g$ | 6 | 12 | 18 | 24 | 30 | 36 | 42 | 48 | 54 | 60 |
|---|---|---|---|---|---|---|---|---|---|---|
| $R(g)$ | 12.50 | 11.25 | 17.05 | 15.09 | 3.42 | 24.50 | 11.28 | 15.59 | 12.80 | 5.20 |

(`python -m twinconj constants`; $S_4(6)=4.15118\ldots$ is the classical
prime-quadruplet constant, a useful check of the machinery.)

**Theorem (explicit local ratio; `paper/`, Thm 1.1).**  For $q\ge5$ the
root counts are determined by divisibility: $\nu_4=2,3,4$ according as
$q\mid g$, $q\mid g^2-4$, or neither; and $\nu_6=\nu_4$ if
$q\mid(g^2-1)(g^2-9)$, $\nu_6=\nu_4+2$ otherwise.  Hence, with
$\Delta(g)=g(g^2-1)(g^2-4)(g^2-9)$,
$\rho_q=q^2(q-\nu_6)/((q-1)^2(q-\nu_4))$ and
$\gamma_q=q^2(q-6)/((q-1)^2(q-4))$,

$$R(g)=R_\infty\,\rho_5(g)\,\rho_7(g)\prod_{q\ge11,\ q\mid\Delta(g)}\frac{\rho_q(g)}{\gamma_q},\qquad
R_\infty=9\prod_{q\ge11}\gamma_q=5.87823926\ldots$$

so $R(g)$ is a universal constant times a *finite* product read off from
$g\bmod5$, $g\bmod7$ and the prime factors of $\Delta(g)$.  Every
coincidence increases $R$, which gives the sharp bounds
$R_{\min}=R_\infty\cdot\frac{25}{48}\cdot\frac{49}{72}=2.08357729\ldots<R(g)\ll(\log\log g)^2$
(the infimum is approached but not attained; the upper order is attained
along $g\equiv1$ mod all small primes).  `twinconj theorems` checks the
formula against the direct product to $10^{-13}$.

### 2.2 Statement

**Conjecture A′.**

1. *(Conditional-probability form.)*
   $$N(X):=\#\{n:\ p_n\le X,\ C_n\in\mathcal T\}\ \sim\ \sum_{5\le p_n\le X}\frac{R(g_n)}{\log C_n\,\log(C_n+2)}\qquad(X\to\infty).$$
2. *(Closed form.)* The averages $\frac1{\pi_2(X)}\sum_{p_n\le X}R(g_n)$
   converge to a constant $\bar R$, and
   $$N(X)\sim\kappa\int_5^X\frac{dt}{(\log t)^2(\log 2t)^2}\sim\kappa\frac{X}{(\log X)^4},\qquad \kappa=2C_2\bar R .$$
   Under the standard Hardy–Littlewood model for consecutive twin gaps the
   limit is the $S_4$-weighted mean of $R$ over gaps, which is a theorem
   about Euler products (`paper/`, Thm 1.3):
   $$\frac6G\sum_{g\le G,\ 6\mid g}S_4(g)\to24C_2^2,\qquad
   \frac6G\sum_{g\le G,\ 6\mid g}S_6(g)\to24C_2^2\,\bar R,\qquad
   \bar R=9\prod_{q\ge5}\frac{q^2(q^2-6q+12)}{(q-1)^2(q-2)^2}=11.18489648\ldots$$
   and therefore
   $$\kappa=2C_2\bar R=\frac{27}{2}\prod_{q\ge5}\frac{q^3(q^2-6q+12)}{(q-1)^4(q-2)}=14.76768314\ldots$$
   The observed averages of $R(g_n)$ are $11.38$ (to $10^8$), $11.347$
   (to $10^9$) and $11.330$ (to $10^{10}$).  The drift is a finite-height
   effect, not a discrepancy: weighting gaps by $S_4(g)e^{-\lambda g}$ with
   $\lambda=2C_2/(\log x)^2$ the twin density, the model mean is $11.366$
   at $x=10^8$, $11.340$ at $10^9$, $11.319$ at $10^{10}$, $11.29$ at
   $10^{12}$, $11.24$ at $10^{20}$, converging to $\bar R$
   (`twinconj theorems`).  The block means on $[2^{28},2^{29})$ and
   $[2^{33},2^{34})$ are $11.335$ and $11.320$.
3. *(Gap-resolved.)* For each fixed $g\equiv0\pmod6$,
   $N_g(X):=\#\{n: p_n\le X,\ g_n=g,\ C_n\in\mathcal T\}\to\infty$, and for
   $g=6$ (where consecutiveness is automatic by Lemma 2) exactly
   $$N_6(X)\sim S_6(6)\int_2^X\frac{dt}{(\log t)^2\,(\log(t+6))^2\,(\log(2t+7))^2},\qquad S_6(6)=51.8958\ldots$$
   this is the Bateman–Horn conjecture for the tuple of Lemma 3.

Part 1 is the *content* of the refinement: it says the propagation event is
governed by the same local–global independence heuristic as every other prime
constellation, with no extra correlation coming from consecutiveness.  It is
the statement that the data test.  Part 2 gives the order of growth the
original note asked for ($\int dt/(\log t)^4$, Remark 4.5) with the constant
identified.  Part 3 is the piece that Hypothesis H addresses.

### 2.3 Data (`python -m twinconj propagation --limit 1e10`, `results/propagation_1e10.txt`)

| range of $p_n$ | pairs | propagating | predicted (A′.1) | ratio | rate | $\bar R$ in block |
|---|---|---|---|---|---|---|
| $[2^{20},2^{21})$ | 6,965 | 356 | 359.9 | 0.989 | 0.0511 | 11.53 |
| $[2^{22},2^{23})$ | 22,643 | 972 | 966.2 | 1.006 | 0.0429 | 11.37 |
| $[2^{24},2^{25})$ | 76,371 | 2,791 | 2,776.6 | 1.005 | 0.0365 | 11.40 |
| $[2^{26},2^{27})$ | 261,752 | 8,205 | 8,163.5 | 1.005 | 0.0313 | 11.37 |
| $[2^{28},2^{29})$ | 904,799 | 24,505 | 24,450.5 | 1.002 | 0.0271 | 11.34 |
| $[2^{30},2^{31})$ | 3,160,113 | 75,420 | 74,894.8 | 1.007 | 0.0239 | 11.33 |
| $[2^{32},2^{33})$ | 11,139,071 | 234,433 | 233,257.3 | 1.005 | 0.0210 | 11.32 |
| $[2^{33},2^{34})$ | 3,534,034 | 71,887 | 71,559.7 | 1.005 | 0.0203 | 11.32 |
| **all $p_n\le10^{10}$** | **27,412,679** | **615,447** | **612,777.0** | **1.0044** | | |

(To $10^9$: 95,606 vs 95,465.5, ratio 1.0015.)  The $\kappa$-integral form
A′.2 gives 612,694.8 (ratio 1.0045).  Gap-resolved to $10^{10}$ (ratios
actual/predicted): $g=6$: 4,527/4,526.8 (1.000); $g=12$: 11,085/10,879.5
(1.019); $g=18$: 12,216/12,156.8 (1.005); $g=30$: 4,837/4,780.7 (1.012);
$g=36$: 9,864/9,731.2 (1.014); $g=60$: 5,450/5,408.5 (1.008); all twenty
gaps $g\le120$ lie in $[0.945,1.036]$ — the factor-of-7 spread in $R(g)$
between $g=30$ and $g=36$ is reproduced.  Gap-6 check of A′.3: 180,529
consecutive gap-6 pairs vs Hardy–Littlewood 181,065.1; 4,527 propagating
gap-6 pairs vs Bateman–Horn 4,540.6 (with $S_6(6)=3\,S(\text{sextuplet})$).

The $D_n$ branch fired exactly once in 27.4 million pairs, at $(3,5)$, as
Lemma 1 requires.

### 2.4 Relation to the original rate law

The original repository fitted the propagation rate by
$6.175(\ln p)^{-2.657}(\ln\ln p)^{2.258}$.  A′ predicts
$\bar R/(\ln 2p)^2$ with $\bar R\approx11.3$; at $p=10^{10},10^{11},10^{12},10^{13}$
the fit gives $0.0196, 0.0163, 0.0137, 0.0117$ and A′ gives
$0.0203, 0.0168, 0.0142, 0.0122$.  The two agree to 3–4 %, so the fitted
exponents are compensating artefacts of a finite range; the correct
description is $c/(\log p)^2$ with $c=\bar R$, which the note's Remark 4.5
anticipated but did not quantify.

---

## 3. Conjecture B′ — effective gap existence

### 3.1 Statement

**Conjecture B′.**

1. *(Effective existence.)* Every $t\in\mathcal T$ with $t\ge5$ has a
   productive gap, and the least one satisfies
   $$d(t)\ \le\ (\log t)^5\log\log t .$$
   (By Lemma 4, $t=3$ must be excluded; no other exclusion is needed.)
2. *(Typical size.)* $\displaystyle\frac1{\pi_2(X)}\sum_{t\le X}\frac{d(t)}{(\log t)^4\log\log t}\to c_B\in(0,\infty)$, with $c_B\approx0.0575$.
3. *(Distribution.)* For $t\to\infty$ and $Y$ in the range
   $Y\asymp(\log t)^{4+o(1)}$,
   $$\Pr\bigl[d(t)>Y\bigr]\approx\exp\bigl(-E_t(Y)\bigr),\qquad E_t(Y)=\sum_{\substack{d\le Y\\ 6\mid d}}6\,A_t(d)\Bigl[\frac{S^-(t)}{\log(d-1)}+\frac{S^+(t)}{\log(d+1)}-\frac{S^{\pm}(t)}{\log(d-1)\log(d+1)}\Bigr],$$
   where $A_t(d)=\bigl[\log(t+d)\log(t+d+2)\log(2t+d+1)\log(2t+d+3)\bigr]^{-1}$
   and $S^-,S^+,S^\pm$ are the singular series of the two 5-tuples and the
   6-tuple with both side conditions.  In particular
   $\max_{t\le X}d(t)\asymp(\log X)^5\log\log X$.

Part 1 replaces $d(t)=o(t)$ — which is very weak (the hypothesis-based
theorem already gives $t^\theta$) — by a Cramér-type bound.  The exponent 5
comes from the model: $E_t(Y)\asymp Y/((\log t)^4\log Y)$, so the least gap
is $\asymp(\log t)^4\log\log t$ typically, and the maximum over the
$\asymp X/(\log X)^2$ twins up to $X$ picks up one more factor $\log X$.

### 3.2 Data (`python -m twinconj gaps --limit 1e10 --model`, `results/gaps_1e10.txt`)

All 27,412,678 lower twins $5\le t\le10^{10}$ have a productive gap.  The
block means track the Poisson model built from the singular series to
within a few percent, and both normalisations are flat:

| range of $t$ | twins | mean $d$ | max $d$ | mean $d/((\ln t)^4\ln\ln t)$ | max $d/((\ln t)^5\ln\ln t)$ | model mean | mean/model |
|---|---|---|---|---|---|---|---|
| $[2^{17},2^{18})$ | 1,153 | 3,518 | 40,884 | 0.0642 | 0.0629 | 3,364 | 1.046 |
| $[2^{21},2^{22})$ | 12,495 | 7,585 | 132,618 | 0.0563 | 0.0672 | 7,883 | 0.962 |
| $[2^{25},2^{26})$ | 140,944 | 16,338 | 366,972 | 0.0577 | 0.0683 | 18,296 | 0.893 |
| $[2^{27},2^{28})$ | 484,968 | 22,526 | 655,722 | 0.0574 | 0.0868 | 21,400 | 1.053 |
| $[2^{29},2^{30})$ | 1,689,477 | 30,518 | 1,062,366 | 0.0574 | 0.0903 | 31,257 | 0.976 |
| $[2^{31},2^{32})$ | 5,928,904 | 40,449 | 1,268,448 | 0.0573 | 0.0791 | 36,843 | 1.098 |
| $[2^{32},2^{33})$ | 11,139,071 | 46,312 | 1,709,784 | 0.0573 | 0.0912 | 43,865 | 1.056 |
| $[2^{33},2^{34})$ | 3,534,034 | 49,872 | 1,728,906 | 0.0574 | 0.0863 | 49,848 | 1.000 |

Record gaps: $d(324{,}301{,}421)=1{,}238{,}658$ (ratio $0.1440$, the largest
observed above $t=17$), $d(9{,}432{,}106{,}511)=1{,}728{,}906$ (the largest
$d$, ratio $0.0863$).  The bound in B′.1 is met with a factor $\ge7$ to
spare for every $t\ge11$.  At the minimal gap the side condition is met by
$d-1$ alone 43.3 %, by $d+1$ alone 42.9 %, by both 13.8 % of the time.

**Independent samples at large height** (`scripts/sample_gaps.py`,
`results/sample_gaps.csv`): 2,000 random lower twins at each of 20, 30, 40,
60, 80, 100 and 150 digits, with $d(t)$ computed exactly by the sieve
scanner.  Under B′.3 the values $u=e^{-E_t(d(t))}$ are uniform on $(0,1)$;
over the 14,000 samples their mean is 0.5033 and the Kolmogorov–Smirnov
distance to uniform is 0.0086 (5 % critical value 0.0115).  The per-size
normalised means $d/((\log t)^4\log\log t)$ are 0.056–0.061, the same
$c_B$ as in the exhaustive range.

**The constructive orbit** $t\mapsto2t+d(t)+1$ from $t=5$
(`scripts/extend_chain.py`, `results/chain_long.csv`) was followed for 1,134
steps to a $t$ of 343 digits; all 4,538 large primes along it are *proved*
(APR-CL, PARI/GP; `results/chain_long_certify.txt`), with ECPP certificates
for the final pair.  Along the orbit the survival values have mean 0.516 and
KS distance 0.038 (critical 0.040), and $d(t)/((\log t)^5\log\log t)$ is
below 0.005 for every $t>10^{12}$: a single sample path of the model,
across 340 orders of magnitude.

---

## 4. The reduction, improved (C′)

**Theorem A** (unchanged; original Theorem 4.4). Hypothesis H for the
admissible 6-tuple $(n,n+2,n+6,n+8,2n+7,2n+9)$ implies Conjecture A, with
infinitely many propagating pairs at gap 6.  By Lemma 3 the same tuple is
admissible for every $g\equiv0\pmod6$, so Hypothesis H also gives infinitely
many lower-twin pairs at any prescribed gap $g$ whose $C$ is a lower twin;
only for $g=6$ is consecutiveness automatic (Lemma 2), which is why the
theorem is stated for gap 6.  Bateman–Horn for the same tuple is A′.3.

**Theorem B** (strengthened; replaces original Lemma 5.2 and Theorem 5.4).
Assume only the *lower-bound* uniform Bateman–Horn hypothesis: for admissible
5-tuples of linear forms $\{d+b_i\}$ with $|b_i|\le X$ and singular series
$S$,
$$\#\{d\le Y:\ \text{all five prime}\}\ \ge\ c\,S\,\frac{Y}{(\log Y)(\log X)^4}\quad\text{for }Y\ge X^{\theta},\ X\ge X_0(\theta),$$
with some $c>0$.  Then **every** $t\in\mathcal T$ with $t\ge t_1(\theta)$ has
$\gg t^\theta/((\log t)^5)$ productive gaps of size $\le t^\theta$; in
particular $d(t)\le t^\theta$ with no exceptional set.

*Proof.* Lemma 5 gives admissibility for all $t\ge11$; Lemma 6 gives
$S(t)\ge S_{\min}$ uniformly, so the hypothesis yields
$\ge c\,S_{\min}\,t^\theta/(\theta\log t\cdot(\log 2t)^4)\to\infty$ productive
$d\le t^\theta$ with $d-1$ prime.  $\square$

Compared with the original: the "thin set of density zero" and the bound
$S(t)\gg(\log t)^{-O(1)}$ are replaced by *no exceptions* and an *absolute*
constant; the hypothesis is weakened from an asymptotic with $o(1)$ error to a
one-sided bound.  Conjecture B′.1 itself (the $(\log t)^5\log\log t$ bound)
lies beyond any Bateman–Horn-type uniformity — it is the analogue of Cramér's
conjecture and is supported by the probabilistic model and the data, not by a
reduction.

---

## 5. Issues found in the original repositories

These do not affect the truth of the conjectures but do affect the reported
evidence and the certificates.

1. **Sieve limit too small for the claimed range** (`twin_prime_prop.py`).
   `small_primes = generate_small_primes(3_000_000)` but the search ran to
   $10^{13}$, and $\sqrt{10^{13}}\approx3.16\cdot10^6>3\cdot10^6$.  Above
   $9\cdot10^{12}$ every product of two primes both larger than
   $3\cdot10^6$ (roughly $10^8$ such numbers in $[9\cdot10^{12},10^{13}]$,
   about 0.4 % of the number of primes there) is reported as prime.  The dyadic block
   $[2^{43},10^{13})$ therefore contains false twins and false propagations
   and should be recomputed with the sieving primes extended past
   $\sqrt{\text{high}}$.
2. **Miller–Rabin base set.** Both scripts use bases $(2,3,5,7,11,13,23)$
   and `prove_section6.py` labels this "deterministic for $n<2^{64}$".  That
   set is not one of the published deterministic sets.  The two smallest
   strong pseudoprimes to bases $2,\dots,13$ and $2,\dots,17$
   ($3{,}474{,}749{,}660{,}383$ and $341{,}550{,}071{,}728{,}321$) do happen
   to be caught by base 23, so no error below $10^{13}$ is known, but there is
   no proof.  `twinconj.primality` uses the first twelve primes, proven
   deterministic below $3.18\cdot10^{23}$.
3. **Segment boundaries.** The twin scan `for i in range(len(is_prime) - 2)`
   never tests the last two positions of a segment.  No twin is lost only
   because $2^{38}+k\cdot1.5\cdot10^8\equiv4\pmod6$ makes those positions
   $\equiv2,3\pmod6$.  Changing `SEGMENT_SIZE` or `RESUME_FROM` would silently
   drop twins.
4. **"B strictly stronger than A"** (`prove_section6.py`, Claim 4; note
   §5).  Withdrawn; see Proposition 7.
5. **"Thin exceptional set"** (note Lemma 5.2).  Empty for $t\ge11$; the
   only exception is $t=5$, and only for the $d-1$ tuple (Lemma 5).  The
   admissibility loop in Claim 5 of the certificate contains dead code
   (`restrict`, `ok_m1`) and checks only $q\le40$; the pigeonhole argument
   makes the check for $q\ge7$ unnecessary.
6. **Fitted rate law.** $6.175(\ln p)^{-2.657}(\ln\ln p)^{2.258}$ is a
   finite-range regression; the model $\bar R/(\ln2p)^2$ with $\bar R\approx11.3$
   matches it to 3–4 % over $10^{10}$–$10^{13}$ with no free parameter
   (§2.4).
7. **Start of the gap conjecture.** "Sufficiently large" can be replaced by
   $t\ge5$ (Lemma 4 shows $t=3$ must be excluded; every $5\le t\le10^{10}$ has a
   productive gap).
8. `final.py` steps `d` by 2 although only $d\equiv0\pmod6$ can be
   productive for $t>3$ (three times the necessary work), and its
   search-bound schedule `t**theta` grows like a power of $t$ although the
   least gap is polylogarithmic; `twinconj chain` replaces it with the exact
   minimal gap.

---

## 6. Reproduction

```bash
pip install -e .
python -m twinconj certify                       # Lemmas 1-7, all PASS
python -m twinconj constants                     # R(g), S_min, kappa model
python -m twinconj propagation --limit 1e9       # Conjecture A' (2 GB RAM, ~1 min)
python -m twinconj gaps --limit 1e8 --model      # Conjecture B' (~1 min)
python -m twinconj chain --steps 25              # constructive orbit
pytest                                           # unit tests
```

Output of these commands is stored under [`results/`](results/).

## References

* P. T. Bateman, R. A. Horn, *A heuristic asymptotic formula concerning the distribution of prime numbers*, Math. Comp. 16 (1962).
* D. Bierton, *A twin-prime propagation conjecture*, Zenodo 10.5281/zenodo.22017371; *A twin-gap existence conjecture*, 10.5281/zenodo.22058355; *Structural reduction …*, 10.5281/zenodo.22063097 (2026).
* G. H. Hardy, J. E. Littlewood, *Partitio Numerorum III*, Acta Math. 44 (1923).
* A. Odlyzko, M. Rubinstein, M. Wolf, *Jumping champions*, Exp. Math. 8 (1999) — the singular-series weighting of consecutive gaps used for $\bar R$.
* J. Sorenson, J. Webster, *Strong pseudoprimes to twelve prime bases*, Math. Comp. 86 (2017).
