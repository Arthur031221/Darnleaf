<p align="center"><img src="src/darnleaf/web/logo.svg" width="72" alt="Darnleaf logo"></p>

<h1 align="center">Darnleaf</h1>

<p align="center"><b>Swap the damaged pages of a scanned PDF for fresh rescans. Match, review, export. Nothing leaves your computer.</b></p>

<p align="center">
<a href="https://github.com/Arthur031221/Darnleaf/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Arthur031221/Darnleaf/ci.yml?branch=main&style=flat-square&color=e8590c&label=ci" alt="CI"></a>
<img src="https://img.shields.io/badge/license-MIT-e8590c?style=flat-square" alt="MIT license">
<img src="https://img.shields.io/badge/python-3.10%2B-e8590c?style=flat-square" alt="Python 3.10+">
<a href="https://arthur031221.github.io/Darnleaf/"><img src="https://img.shields.io/badge/try-the%20replay%20demo-1d1a16?style=flat-square" alt="Replay demo"></a>
</p>

<p align="center"><img src="assets/demo.gif" width="860" alt="Darnleaf matching seven rescans to a 40-page booklet, reviewing an overlay and exporting a repaired PDF"></p>

[English](README.md) | [Traditional Chinese](README.zh-TW.md) | [Simplified Chinese](README.zh-CN.md) | [Japanese](README.ja.md) | [Korean](README.ko.md) | [Spanish](README.es.md) | [French](README.fr.md) | [German](README.de.md) | [Portuguese (Brazil)](README.pt-BR.md)

You've got an old scanned PDF with a few ruined pages, and fresh scans of those pages in no particular order. Darnleaf suggests which page each rescan replaces, shows you the evidence, and writes a repaired PDF plus a JSON receipt of every change.

- **Not an auto-fixer.** Each match is labeled Clear, Check or None. Export stays locked until you confirm every Check. Blank pages are always Check, and so is any page where the runner-up scores close.
- **Not a rewrite.** Pages you didn't touch are the original page objects, saved without re-rendering. The original file is never written to.
- **Not a service.** It's a small server that binds only to loopback (127.0.0.1 by default). No account, no upload, no telemetry, and the page loads no remote fonts or scripts.

## Try it

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf serve
```

Press **Try the bundled sample** to run the whole flow on a synthetic 40-page booklet, or drop in your own files. The [replay demo](https://arthur031221.github.io/Darnleaf/) plays a recorded run of that sample in your browser and doesn't take files. To skip the upload step, pass the files: `darnleaf serve original.pdf rescans/*.jpg` loads them and starts matching before the browser opens.

From a terminal:

```console
$ darnleaf sample job
wrote job/original.pdf, 7 rescans and truth.json
$ darnleaf match job/original.pdf job/rescans/*.jpg
rescan                        page  status  reason
rescan-01.jpg                   33  check   page 35 scores almost as high (margin 0.02)
rescan-02.jpg                   11  clear   205 consistent features, margin 0.60
rescan-03.jpg                    2  check   blank pages carry no evidence: confirm the position yourself
rescan-04.jpg                   22  clear   428 consistent features, margin 0.94
rescan-05.jpg                   31  check   page 32 scores almost as high (margin 0.05)
rescan-06.jpg                   27  clear   230 consistent features, margin 0.78
rescan-07.jpg                    -  none    no original page shares enough features or text with this rescan
$ darnleaf apply job/original.pdf job/rescans/*.jpg -o job/repaired.pdf
replaced 3 of 40 pages -> job/repaired.pdf
receipt -> job/repaired.receipt.json
```

`apply` used only the three Clear matches. The Check ones wait for you in the review screen, or for `--assign FILE=PAGE`.

## Before and after

| By hand | With Darnleaf |
| --- | --- |
| Open both files and work out which photo belongs to which page | Suggested page per rescan, with the matched features and an overlay of old ink against new ink |
| Rotate sideways and upside-down scans | Quarter turns are found from the match |
| Square up a phone photo taken at an angle | The perspective is corrected when the page is aligned |
| Resize and position each image to fit its page | Aligned onto the old page's frame, or fitted with white padding |
| Insert the new page, delete the old one, hope the bookmarks survive | The page object stays in place, so bookmarks and links that point at it still work (covered by a test) |
| No record of what changed | A receipt with SHA-256 of the original, the output and every rescan, plus the evidence for each swap |

## Benchmarks

Measured on synthetic booklets built from public-domain text (*Pride and Prejudice*): 90 rescans over ten held-out seeds (101 to 110). Pages are damaged with a coffee ring, a crease and a smear. Rescans get skew, noise, blur and random quarter turns. Thresholds were tuned on seeds 1 to 3 only. Reproduce with `python scripts/benchmark.py --seeds 101-110`.

| Kind of page | Rescans | Clear | Check | None | Wrong Clear | Right answer listed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Text | 43 | 42 | 1 | 0 | 0 | 43 |
| Figure | 3 | 3 | 0 | 0 | 0 | 3 |
| Repeated form | 24 | 0 | 24 | 0 | 0 | 24 |
| Blank page | 10 | 0 | 9 | 1 | 0 | 9 |
| Not in the booklet | 10 | 0 | 0 | 10 | 0 | 10 (None) |
| **All** | **90** | **45** | **34** | **11** | **0** | **89 of 90** |

None of the 45 Clear matches was wrong. With only 45 trials, the real wrong rate could still be as high as about 6.7% (the rule of three, 95% confidence). The top suggestion was right (or correctly None) for 95.6% of rescans, and a Check match is still a suggestion you review.

Treat these numbers as an upper bound. The original and the rescan come from the same clean bitmap, so they agree better than a real flatbed rescan of a worn page would. Real documents will likely give more Check and None results, not fewer. All 45 Clear matches are text and figure pages with distinct content. The form and blank cases are the same fixed pages in every seed, so they're fewer independent trials than the counts suggest. Generating the bundled sample and then running match and apply on its 7 rescans and 40 pages took about 20 seconds in total on the 3-core Linux machine that built it. Larger jobs scale with pages times rescans in the shortlist pass.

Phone photos are rarely square to the page. With `--tilt 0.04`, every rescan in the same ten seeds is warped as if photographed at an angle, each corner moved by up to 4% of the page. Version 0.4.0 gives 46 Clear and none wrong, and the top suggestion is right (or correctly None) for 77 of 90. Version 0.3.0 gave 31 Clear and 46 of 90, because it only modelled a flat scan. Blank pages fall to None under tilt, since the desk edge reads as ink, so place them by hand. The run is in `docs/benchmark-tilted.json`.

## Install

<details open>
<summary>pipx (recommended)</summary>

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf --version
```

Python 3.10 or newer. The dependencies are PDFium (pypdfium2), pikepdf, OpenCV (headless), NumPy and Pillow. It isn't on PyPI. The full suite runs on Linux. The CLI, export and imaging tests also run on macOS and Windows in CI, but the matcher has only been exercised on Linux.
</details>

<details>
<summary>pip in a virtual environment</summary>

```sh
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install git+https://github.com/Arthur031221/Darnleaf
```
</details>

<details>
<summary>From a clone (to hack on it)</summary>

```sh
git clone https://github.com/Arthur031221/Darnleaf
cd Darnleaf
pip install -e ".[dev]"
pytest
```
</details>

<details>
<summary>Read the text as a second signal (optional OCR)</summary>

```sh
pipx install "darnleaf[ocr] @ git+https://github.com/Arthur031221/Darnleaf"
```

Or install Tesseract and have it on your PATH. Then tick "Also read the text" in the UI or pass `--ocr`. Text can raise or lower a score, but it can't create a match on its own.
</details>

## Common commands

| Task | Command |
| --- | --- |
| Open the review screen | `darnleaf serve` |
| Open it with files already loaded | `darnleaf serve original.pdf rescans/*.jpg` |
| Print suggestions | `darnleaf match original.pdf rescans/*.jpg` |
| Print them as JSON | `darnleaf match original.pdf rescans/*.jpg --json` |
| Write the repaired PDF from Clear matches | `darnleaf apply original.pdf rescans/*.jpg -o fixed.pdf` |
| Also take Check matches | add `--accept-check` |
| Force one rescan onto page 12 | add `--assign scan-07.jpg=12` |
| Keep the rescan unwarped | add `--mode fit` |
| Make a synthetic test job | `darnleaf sample demo/` |

More in [docs/usage.md](docs/usage.md) and [docs/how-it-works.md](docs/how-it-works.md).

## Limits

- Refuses encrypted PDFs, digitally signed PDFs, PDFs with form fields, and pages with a `Rotate` that isn't a multiple of 90.
- Up to 200 pages in the original, 40 rescans, 400 MB for the original and 60 MB per rescan.
- Pages with annotations aren't replaced unless you say the annotations may be dropped.
- Two near-identical pages can't be told apart from images, so they become Check when the runner-up scores close. A blank page carries no evidence and is always Check.
- The interface is translated into nine languages, including the reason under each match. The output of `darnleaf match` is English.
- iPhone HEIC photos need `pip install "darnleaf[heic]"`. Everything else (PNG, JPEG, TIFF, BMP, WebP, PDF) works without it.

## Contributing

Issues and pull requests are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md). A wrong Clear match is worse than a missed one, so changes to the matcher need held-out numbers. MIT license, see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Assisted by Claude/Codex.
