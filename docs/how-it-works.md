# How it works

```
original.pdf --render--> page signatures --+
                                           +--> shortlist -> verify -> assign -> review -> export
rescans -------load----> rescan signatures-+
```

## Signatures

Every original page is rendered with PDFium and every rescan is loaded, then both are reduced to the same working size (longest side 1000 px). A signature holds SIFT keypoints and descriptors, a spread-out subset of them for the cheap pass, an ink mask, and whether the page is blank. Rescans are cropped to the paper first, so a dark scanner bed does not produce features.

## Matching

1. **Shortlist.** The coarse feature subset of the rescan is matched against every page and counted for geometric consistency. The ten best pages go on.
2. **Verify.** Full feature matching with Lowe's ratio test, then a RANSAC similarity transform (`estimateAffinePartial2D`). A phone photo taken at a slant is not a similarity, so a RANSAC homography (`findHomography`) is tried too. It replaces the similarity only if it explains at least 25% more of the matches and the corners of the rescan land within 12% of the page diagonal of where the best similarity puts them, so a flat scan never takes the looser model. The transform must be plausible: scale between 0.7 and 1.4, and within 12 degrees of a right angle, measured at the middle of the rescan. The nearest right angle gives the rescan's rotation, so photos taken sideways or upside down work.
3. **Agreement.** The rescan's ink mask is warped onto the page and compared. This is only a gate (at least 0.65), not a ranking signal.
4. **Score.** `1 - exp(-inliers / 150)`, slightly scaled by agreement. With OCR, 65% image and 35% word overlap.
5. **Assign.** The Hungarian algorithm gives each page to at most one rescan, over candidates with at least 25 consistent features.
6. **Label.** Clear needs a score of 0.55, a margin of 0.12 over the runner-up, and no rival rescan ranking the same page first. Everything else with a candidate is Check.

Blank pages are always Check and text alone can never create an assignment.

## Export

Export opens the original with pikepdf and swaps each chosen page's content and resources in place, keeping the page object. Inherited `MediaBox`, `CropBox` and `Rotate` values are resolved, and all four `Rotate` cases place the image upright. Before anything is written, a preflight refuses:

- encrypted files and files with digital signatures
- forms that have fields (AcroForm)
- `Rotate` values that are not a multiple of 90
- anything over the limits below

## The local server

`darnleaf serve` uses the standard library's `ThreadingHTTPServer` and refuses any `--host` that is not loopback (127.0.0.0/8, `::1` or `localhost`). A random token is set in an HttpOnly, SameSite=Strict cookie and must come back in an `X-Darnleaf-Token` header on every write. The `Host` header is checked against an allow-list (this blocks DNS rebinding), responses carry a strict CSP, and uploads are raw bodies with size limits. Nothing is fetched from the network, and the page loads no remote fonts or scripts. The token keeps other websites in your browser out. It does not hide anything from other programs running as you on the same machine, because they can fetch `/` and read it. PDFium is not thread-safe, so every call into it goes through one lock.

## Limits

| Limit | Value |
| --- | --- |
| Pages in the original | 200 |
| Rescans per job | 40 |
| Original file size | 400 MB |
| Rescan file size | 60 MB |
| Image size | 120 megapixels |

## What it does not do

- It does not repair a page. It replaces one with a rescan you provide.
- It does not match rescans of a different edition, a different language or a different layout. Those come back None.
- Two near-identical pages (forms, tables with changed digits) cannot be told apart from the images. When the runner-up scores within the margin they are Check. A blank page is always Check.
- The matcher's `reason` text is English only. The interface around it is translated.
- The hosted demo at https://arthur031221.github.io/Darnleaf/ is a replay of a real run on the bundled sample. It does not accept files.

## Benchmark

`scripts/benchmark.py` builds synthetic booklets from public-domain text, damages some pages, rescans them with skew, noise and rotation, and scores the matcher against the known answers. Thresholds were tuned on seeds 1 to 3. The held-out run (seeds 101 to 110, 90 rescans) is in `docs/benchmark-heldout.json`. `--tilt 0.04` photographs every rescan at a slant (each corner moves by up to 4% of the page) and `docs/benchmark-tilted.json` holds that run.

The rescan and the original scan come from the same clean bitmap, so their features agree better than a real flatbed rescan of a real worn page would. Treat these numbers as an upper bound on real-world quality.
