## Darnleaf 0.4.0

- Rescans photographed at a slant now match and align. The matcher tries a perspective fit next to the flat one and uses it only when it explains clearly more of the matches, so flat scans give the same results as before. On ten held-out seeds with every rescan tilted (`scripts/benchmark.py --tilt 0.04`) the Clear count rises from 31 to 46 of 90 and the right answer comes first for 77 of 90 instead of 46, with no wrong Clear in either run. The held-out result on flat scans is unchanged.
- Aligned export straightens a slanted photo onto the page frame, and the overlay and matched-features views use the same fit.
- The review list updates in place instead of reloading every thumbnail after each confirm, and pictures fade in once they load.
- `scripts/benchmark.py` has a `--tilt` option, and the tilted run is saved in `docs/benchmark-tilted.json`.

Install: `pipx install git+https://github.com/Arthur031221/Darnleaf@v0.4.0`, or install the attached wheel.
