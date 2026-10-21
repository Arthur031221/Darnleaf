# Contributing

Darnleaf is small on purpose. Issues and pull requests that keep it local, reviewable and honest are welcome.

## Set up

```sh
git clone https://github.com/Arthur031221/Darnleaf
cd Darnleaf
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Check before you push

```sh
ruff check src scripts tests
pytest                              # unit, integration and server tests, about two minutes
node --test tests/e2e/ui.test.mjs   # needs Chrome; set CHROME_BIN if it is not "google-chrome"
```

## Ground rules

- **Nothing leaves the machine.** No telemetry, no remote fonts, no CDN scripts. The server binds 127.0.0.1 only.
- **Never write to the original.** Export saves a new file and a receipt.
- **A wrong swap is worse than a missed one.** A change to the matcher has to keep the held-out result at zero wrong "clear" matches. Run `python scripts/benchmark.py --seeds 101-110` and put the numbers in the pull request. Tune on seeds 1-3 only.
- **Strings.** A new UI string goes into all nine files in `src/darnleaf/web/locales/`. The e2e test fails on a missing key.
- **Engine reasons are English only.** The matcher's `reason` text is not translated, though the UI labels around it are.

## Reporting a bad match

Open an issue with the receipt JSON (it holds hashes and scores, no page content) and, if you can share it, the page that was matched wrongly. Please do not attach documents that are private.
