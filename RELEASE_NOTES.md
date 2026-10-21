## Darnleaf 0.3.0

- The bundled sample button now loads the sample and starts matching in one press. Clear and sample are disabled while a match runs.
- The reason shown under each match is translated with the interface, in all nine languages. The matcher now returns a `reason_key` and `reason_args` next to the English `reason`, so the JSON output stays compatible.
- `darnleaf serve original.pdf rescans/*.jpg` loads the files and starts matching before the browser opens. A bad path is reported in the terminal and the server does not start.
- iPhone HEIC and HEIF photos are accepted with `pip install "darnleaf[heic]"`. Without the extra, the error says how to enable it.
- CI also runs the portable tests on macOS and Windows.
- A test now checks that every locale file has the same keys and placeholders.

Install: `pipx install git+https://github.com/Arthur031221/Darnleaf@v0.3.0`, or install the attached wheel.

