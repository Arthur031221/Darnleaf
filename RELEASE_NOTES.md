## Darnleaf 0.2.0

- Fixed: downloading the repaired PDF or receipt failed when the original's file name had non-Latin characters (for example Chinese, Japanese or Korean). The server now sends an ASCII name plus the UTF-8 name.
- Fixed: on a phone the review screen scrolled sideways.
- Review is faster: Confirm jumps to the next rescan that still needs a check. Keys: j and k to move, 1 to 8 to pick a candidate page, c to confirm.
- Accessibility: progress and export status are announced, and the view tabs support the arrow keys.
- The replay demo shows the sample button first, and a page without a bundled preview shows a placeholder instead of a broken image.
- The demo page has a description and share preview tags.

Install: `pipx install git+https://github.com/Arthur031221/Darnleaf@v0.2.0`, or install the attached wheel.
