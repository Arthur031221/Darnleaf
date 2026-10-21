# Using Darnleaf

## The review screen

```sh
darnleaf serve            # http://127.0.0.1:8765, opens your browser
darnleaf serve --port 9000 --no-open
darnleaf serve original.pdf rescans/*.jpg   # load the files and start matching, so the browser opens on the review
```

With files on the command line the server reads them before it starts listening, so a bad path or an unreadable PDF is reported in the terminal and nothing opens. Give the original and at least one rescan, or neither. `--ocr` is accepted here too.

`--host` only accepts loopback addresses (127.0.0.0/8, `::1`, `localhost`). Anything else is refused.

1. Drop the damaged PDF on the left box and the fresh rescans (photos, images or PDFs, any order) on the right box. PNG, JPEG, TIFF, BMP and WebP work out of the box. iPhone HEIC photos need `pip install "darnleaf[heic]"`, or export them as JPEG first.
2. Press **Find matches**. Each rescan gets a suggested page and one of three labels. **Try the bundled sample** loads a synthetic booklet and does this step for you.
3. Click a rescan to see why. Three views: side by side, an overlay (orange is ink only the old page has, blue is ink only the rescan has) and the matched features. Other plausible pages are listed under the view, and you can type any page number yourself. **Zoom** (or a click on the picture) opens both pages at full size in one window, and they scroll together so you can compare a stain or a crease at the same spot. Once there is something to review, the file panel folds into one line, and **Change files** opens it again.
4. Confirm every rescan labelled **Check**. The export button stays locked until you do. Confirming jumps to the next rescan that still needs a check. Keys: `j` and `k` move between rescans (the arrow keys too, while the list has focus), `1` to `8` pick a candidate page, `c` confirms, `z` opens a closer look.
5. Press **Write repaired PDF**. Download the PDF and the receipt.

| Label | What it means | Needs your confirmation |
| --- | --- | --- |
| Clear | Plenty of consistent features, a wide margin over the next page, and no other rescan claims the same page. | No |
| Check | A match exists but it is weak, close to another page, contested, or the page is blank. | Yes |
| None | No page shares enough features with this rescan. | Not used unless you assign a page by hand |

Repeated forms and blank pages are always **Check**. Two copies of the same form differ in a handful of digits and a blank page carries no evidence, so Darnleaf will not guess between them.

## Placement

- **Align to the original page** (default) warps the rescan onto the page's frame, so margins and size match the neighbours. A photo taken at a slant is straightened in the same step. If the alignment cannot be computed it falls back to fit and the receipt says `"placement": "fit"`.
- **Fit inside the page** keeps the rescan unwarped and pads it with white to the page's aspect ratio.

Pages you did not replace are the original page objects, saved without re-rendering. Annotations on a replaced page would be lost, so export refuses until you tick "drop annotations" (CLI: `--drop-annotations`).

## Command line

```sh
darnleaf match original.pdf rescans/*.jpg            # table of suggestions
darnleaf match original.pdf rescans/*.jpg --json     # the same, with the top candidates and their scores
darnleaf apply original.pdf rescans/*.jpg -o fixed.pdf
darnleaf apply original.pdf a.jpg b.jpg -o fixed.pdf --assign a.jpg=12 --accept-check
darnleaf sample demo/                                # a synthetic damaged booklet to try things on
```

`apply` only uses matches labelled Clear. `--accept-check` adds the Check ones and `--assign FILE=PAGE` forces a page (1-based). Each choice is written into the receipt as `confirmed_by`. The receipt lands next to the output as `fixed.receipt.json`. Exit code 2 means the input was refused or nothing was safe to replace.

## The receipt

```json
{
  "tool": "darnleaf 0.3.0",
  "original": { "file": "original.pdf", "sha256": "...", "pages": 40 },
  "output":   { "file": "repaired.pdf", "sha256": "...", "pages": 40 },
  "replaced": [
    {
      "page": 11,
      "replacement": "rescan-02.jpg",
      "replacement_sha256": "...",
      "quarter_turns_clockwise": 0,
      "placement": "aligned",
      "evidence": { "page": 11, "score": 0.74, "inliers": 205, "agreement": 0.97, "quarter_turns": 0, "angle": 1.1, "scale": 1.02 },
      "confirmed_by": "matcher: clear"
    }
  ],
  "untouched_pages": 34
}
```

## Reading text as a second signal

Rescans of text pages usually match on visual features alone. If you also want word overlap as a second signal, install an OCR engine and tick the box (CLI: `--ocr`):

```sh
pipx install "darnleaf[ocr] @ git+https://github.com/Arthur031221/Darnleaf"   # RapidOCR, or
sudo apt install tesseract-ocr                                                # any tesseract on PATH
```

Text can raise or lower a score. It cannot create a match that the images do not support.
