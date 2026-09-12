# Run sheet: 16-core / 128 GB desktop

## Windows (PowerShell), from the unpacked folder

Setup, once:

    python -m pip install -r requirements.txt
    python -m pytest -q                    # ~2 min, expect "45 passed"

PARI/GP (only needed for step 3): download and run the 64-bit installer
`Pari64-2-17-4.exe` from https://pari.math.u-bordeaux.fr/download.html
(no `apt` on Windows).  `certify_chain.py` finds `gp.exe` in the default
install folder by itself; otherwise pass `--gp "C:\Program Files (x86)\Pari64-2-17-4\gp.exe"`.

Open one PowerShell window per step; every step resumes with the same
command if interrupted.  Use 15 workers for 1-3 and let 4 (single-threaded)
have the spare core and the RAM.

1. Extend the orbit t -> 2t + d(t) + 1 (starts from the 400 steps in results/):

    python scripts\extend_chain.py --csv results\chain_long.csv --steps 1000 --workers 15
    # later, overnight:
    python scripts\extend_chain.py --csv results\chain_long.csv --steps 1500 --workers 15

2. Independent random twins, d(t) vs the Poisson model (KS test):

    python scripts\sample_gaps.py --digits 20 30 40 60 80 100 150 --samples 2000 --workers 15 --out results\sample_gaps.csv

3. Prove every prime of the chain with PARI and write ECPP certificates for the end:

    python scripts\certify_chain.py results\chain_long.csv --workers 15 --ecpp results\chain_long_final.cert

4. Exhaustive d(t) and propagation counts to 1e10 (~40 GB and ~20 GB RAM):

    .\scripts\run_exhaustive.ps1 1e10
    # if PowerShell refuses to run scripts:  powershell -ExecutionPolicy Bypass -File .\scripts\run_exhaustive.ps1 1e10

5. Refresh the chain report and send the results back:

    python -m twinconj verify-chain results\chain_long.csv --out results\verify_chain_long.txt
    git add results; git commit -m "large-machine runs"; git push

Nothing here uses the GPU.

## Linux / WSL

Same commands with `/` in paths, `python3` if `python` is not defined,
`sudo apt install pari-gp` for PARI, and `bash scripts/run_exhaustive.sh 1e10`
for step 4.
