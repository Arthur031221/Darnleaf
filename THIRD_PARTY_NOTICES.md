# Third-party notices

## Bundled data

- `src/darnleaf/data/sample_text.txt.gz` (gzip) is an excerpt of *Pride and Prejudice* by Jane Austen, taken from Project Gutenberg. The work is in the public domain in the United States. It is used only to draw the synthetic sample booklet.
- The demo files in `site-data/demo/` are generated from that synthetic booklet by `scripts/build_demo.py`. No real document is included.

## Runtime dependencies (installed, not vendored)

| Package | License |
| --- | --- |
| pypdfium2 (bundles PDFium) | Apache-2.0 / BSD-3-Clause |
| pikepdf (wraps QPDF) | MPL-2.0 |
| opencv-python-headless | Apache-2.0 |
| numpy | BSD-3-Clause |
| Pillow | HPND |
| rapidocr-onnxruntime (optional `ocr` extra) | Apache-2.0 |

Tesseract, if you have it on PATH, is run as a separate program and is not shipped with Darnleaf.

The sample booklet draws with DejaVu fonts when they are installed on the machine (Bitstream Vera license). They are not bundled.
